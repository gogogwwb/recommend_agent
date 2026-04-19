"""
Main Graph (Orchestrator) - LangGraph 1.0.0 Implementation

This module implements the Main Graph that orchestrates the three subgraphs:
- Profile Subgraph: Collects user profile information
- Recommendation Subgraph: Generates product recommendations
- Compliance Subgraph: Performs compliance checks

Key Features:
- State transformation between MainState and subgraph-specific states
- Sequential subgraph invocation (Profile → Recommendation → Compliance)
- PostgresSaver checkpointer integration for session persistence
- Error handling and recovery

Architecture:
- Uses MainState (TypedDict) for overall state management
- Each subgraph node transforms MainState to subgraph-specific state
- Invokes subgraph and merges results back to MainState

Requirements: 4.1, 4.4
"""
import logging
from typing import Dict, Any, List, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

from models.subgraph_states import (
    MainState,
    ProfileState,
    RecommendationState,
    ComplianceState,
    create_initial_main_state,
    create_initial_profile_state,
    create_initial_recommendation_state,
    create_initial_compliance_state,
)
from models.user import UserProfile
from models.product import RecommendationResult
from models.compliance import ComplianceCheck, DisclosureInfo
from agents.profile_subgraph import create_profile_subgraph
from agents.recommendation_subgraph import create_recommendation_subgraph
from agents.compliance_subgraph import create_compliance_subgraph
from utils.checkpointer import get_checkpointer, CheckpointerError

logger = logging.getLogger(__name__)


# ==================== Constants ====================

# Agent execution order
AGENT_ORDER = ["profile", "recommendation", "compliance"]

# Maximum retry attempts for subgraph execution
MAX_RETRY_ATTEMPTS = 2


# ==================== State Transformation Functions ====================

def transform_to_profile_state(state: MainState) -> ProfileState:
    """
    Transform MainState to ProfileState
    
    Extracts relevant fields from MainState to create ProfileState
    for the Profile Subgraph.
    
    Args:
        state: Current MainState
        
    Returns:
        ProfileState for Profile Subgraph
    """
    return ProfileState(
        # Conversation management
        messages=state.get("messages", []),
        user_id=state.get("user_id", ""),
        session_id=state.get("session_id", ""),
        
        # User profile (output)
        user_profile=state.get("user_profile"),
        
        # Slot extraction
        slots=state.get("slots", {}),
        missing_slots=state.get("missing_slots", []),
        
        # Risk preference
        risk_preference=state.get("risk_preference"),
        risk_score=state.get("risk_score"),
        
        # Existing coverage
        existing_coverage=state.get("existing_coverage", []),
        
        # Intent recognition
        current_intent=state.get("current_intent"),
        
        # Control flow
        profile_complete=state.get("profile_complete", False),
        error=None,  # Reset error for subgraph
    )


def transform_from_profile_state(
    main_state: MainState,
    profile_result: ProfileState
) -> Dict[str, Any]:
    """
    Transform ProfileState result back to MainState updates
    
    Merges the Profile Subgraph results back into MainState.
    
    Args:
        main_state: Current MainState
        profile_result: Result from Profile Subgraph
        
    Returns:
        Dict with MainState field updates
    """
    updates = {}
    
    # User profile
    if profile_result.get("user_profile"):
        updates["user_profile"] = profile_result["user_profile"]
    
    # Profile completion status
    updates["profile_complete"] = profile_result.get("profile_complete", False)
    
    # Slots
    if profile_result.get("slots"):
        updates["slots"] = profile_result["slots"]
    
    if profile_result.get("missing_slots"):
        updates["missing_slots"] = profile_result["missing_slots"]
    
    # Risk preference
    if profile_result.get("risk_preference"):
        updates["risk_preference"] = profile_result["risk_preference"]
    
    if profile_result.get("risk_score"):
        updates["risk_score"] = profile_result["risk_score"]
    
    # Existing coverage
    if profile_result.get("existing_coverage"):
        updates["existing_coverage"] = profile_result["existing_coverage"]
    
    # Intent
    if profile_result.get("current_intent"):
        updates["current_intent"] = profile_result["current_intent"]
    
    # Error handling
    if profile_result.get("error"):
        updates["error"] = profile_result["error"]
    
    return updates


def transform_to_recommendation_state(state: MainState) -> RecommendationState:
    """
    Transform MainState to RecommendationState
    
    Extracts relevant fields from MainState to create RecommendationState
    for the Recommendation Subgraph.
    
    Args:
        state: Current MainState
        
    Returns:
        RecommendationState for Recommendation Subgraph
    """
    user_profile = state.get("user_profile")
    
    return RecommendationState(
        # Basic info
        user_id=state.get("user_id", ""),
        session_id=state.get("session_id", ""),
        
        # User profile (input)
        user_profile=user_profile,
        
        # Risk preference
        risk_preference=state.get("risk_preference"),
        risk_score=state.get("risk_score"),
        
        # Existing coverage
        existing_coverage=state.get("existing_coverage", []),
        
        # Recommendation results (output)
        recommendations=state.get("recommendations", []),
        explanations=[],
        
        # Coverage gap analysis
        coverage_gap=state.get("coverage_gap"),
        
        # Recommendation constraints
        recommendation_constraints=state.get("recommendation_constraints"),
        excluded_products=state.get("excluded_products", []),
        
        # Control flow
        recommendation_generated=state.get("recommendation_generated", False),
        error=None,  # Reset error for subgraph
    )


def transform_from_recommendation_state(
    main_state: MainState,
    recommendation_result: RecommendationState
) -> Dict[str, Any]:
    """
    Transform RecommendationState result back to MainState updates
    
    Merges the Recommendation Subgraph results back into MainState.
    
    Args:
        main_state: Current MainState
        recommendation_result: Result from Recommendation Subgraph
        
    Returns:
        Dict with MainState field updates
    """
    updates = {}
    
    # Recommendations
    if recommendation_result.get("recommendations"):
        updates["recommendations"] = recommendation_result["recommendations"]
    
    # Recommendation generated flag
    updates["recommendation_generated"] = recommendation_result.get(
        "recommendation_generated", False
    )
    
    # Coverage gap
    if recommendation_result.get("coverage_gap"):
        updates["coverage_gap"] = recommendation_result["coverage_gap"]
    
    # Error handling
    if recommendation_result.get("error"):
        updates["error"] = recommendation_result["error"]
    
    return updates


def transform_to_compliance_state(state: MainState) -> ComplianceState:
    """
    Transform MainState to ComplianceState
    
    Extracts relevant fields from MainState to create ComplianceState
    for the Compliance Subgraph.
    
    Args:
        state: Current MainState
        
    Returns:
        ComplianceState for Compliance Subgraph
    """
    return ComplianceState(
        # Basic info
        user_id=state.get("user_id", ""),
        session_id=state.get("session_id", ""),
        
        # User profile (input)
        user_profile=state.get("user_profile"),
        
        # Recommendations (input)
        recommendations=state.get("recommendations", []),
        
        # Compliance checks (output)
        compliance_checks=state.get("compliance_checks", []),
        compliance_passed=state.get("compliance_passed", False),
        
        # Disclosure info (output)
        disclosure_info=state.get("disclosure_info", []),
        
        # Filtered recommendations (output)
        filtered_recommendations=[],
        
        # Error
        error=None,  # Reset error for subgraph
    )


def transform_from_compliance_state(
    main_state: MainState,
    compliance_result: ComplianceState
) -> Dict[str, Any]:
    """
    Transform ComplianceState result back to MainState updates
    
    Merges the Compliance Subgraph results back into MainState.
    
    Args:
        main_state: Current MainState
        compliance_result: Result from Compliance Subgraph
        
    Returns:
        Dict with MainState field updates
    """
    updates = {}
    
    # Compliance checks
    if compliance_result.get("compliance_checks"):
        updates["compliance_checks"] = compliance_result["compliance_checks"]
    
    # Compliance passed flag
    updates["compliance_passed"] = compliance_result.get("compliance_passed", False)
    
    # Disclosure info
    if compliance_result.get("disclosure_info"):
        updates["disclosure_info"] = compliance_result["disclosure_info"]
    
    # Filtered recommendations (replace original with filtered)
    if compliance_result.get("filtered_recommendations"):
        updates["recommendations"] = compliance_result["filtered_recommendations"]
    
    # Error handling
    if compliance_result.get("error"):
        updates["error"] = compliance_result["error"]
    
    return updates


# ==================== Node Functions ====================

async def profile_node(state: MainState) -> Dict[str, Any]:
    """
    Profile Subgraph Node
    
    This node:
    1. Transforms MainState to ProfileState
    2. Invokes the Profile Subgraph
    3. Transforms results back to MainState updates
    
    Args:
        state: Current MainState
        
    Returns:
        Dict with MainState field updates
    """
    logger.info(f"Profile node executing for session {state.get('session_id')}")
    
    try:
        # Update current agent
        updates = {"current_agent": "profile"}
        
        # Check if profile is already complete
        if state.get("profile_complete"):
            logger.info("Profile already complete, skipping profile subgraph")
            return updates
        
        # Transform to ProfileState
        profile_input = transform_to_profile_state(state)
        
        # Create and invoke Profile Subgraph
        profile_subgraph = create_profile_subgraph()
        
        logger.debug("Invoking Profile Subgraph...")
        result = await profile_subgraph.ainvoke(profile_input)
        
        # Transform results back to MainState
        result_updates = transform_from_profile_state(state, result)
        updates.update(result_updates)
        
        logger.info(
            f"Profile Subgraph complete: profile_complete={result.get('profile_complete')}"
        )
        
        return updates
        
    except Exception as e:
        logger.error(f"Error in profile_node: {e}")
        return {
            "error": f"画像收集失败: {str(e)}",
            "current_agent": "profile",
        }


async def recommendation_node(state: MainState) -> Dict[str, Any]:
    """
    Recommendation Subgraph Node
    
    This node:
    1. Transforms MainState to RecommendationState
    2. Invokes the Recommendation Subgraph
    3. Transforms results back to MainState updates
    
    Args:
        state: Current MainState
        
    Returns:
        Dict with MainState field updates
    """
    logger.info(f"Recommendation node executing for session {state.get('session_id')}")
    
    try:
        # Update current agent
        updates = {"current_agent": "recommendation"}
        
        # Check if profile is complete
        if not state.get("profile_complete"):
            logger.warning("Profile not complete, cannot generate recommendations")
            return {
                "error": "用户画像未完成，无法生成推荐",
                "current_agent": "recommendation",
            }
        
        # Check if recommendations already generated
        if state.get("recommendation_generated"):
            logger.info("Recommendations already generated, skipping")
            return updates
        
        # Transform to RecommendationState
        recommendation_input = transform_to_recommendation_state(state)
        
        # Create and invoke Recommendation Subgraph
        recommendation_subgraph = create_recommendation_subgraph()
        
        logger.debug("Invoking Recommendation Subgraph...")
        result = await recommendation_subgraph.ainvoke(recommendation_input)
        
        # Transform results back to MainState
        result_updates = transform_from_recommendation_state(state, result)
        updates.update(result_updates)
        
        logger.info(
            f"Recommendation Subgraph complete: "
            f"{len(result.get('recommendations', []))} recommendations generated"
        )
        
        return updates
        
    except Exception as e:
        logger.error(f"Error in recommendation_node: {e}")
        return {
            "error": f"推荐生成失败: {str(e)}",
            "current_agent": "recommendation",
        }


async def compliance_node(state: MainState) -> Dict[str, Any]:
    """
    Compliance Subgraph Node
    
    This node:
    1. Transforms MainState to ComplianceState
    2. Invokes the Compliance Subgraph
    3. Transforms results back to MainState updates
    
    Args:
        state: Current MainState
        
    Returns:
        Dict with MainState field updates
    """
    logger.info(f"Compliance node executing for session {state.get('session_id')}")
    
    try:
        # Update current agent
        updates = {"current_agent": "compliance"}
        
        # Check if recommendations exist
        if not state.get("recommendations"):
            logger.warning("No recommendations to check compliance for")
            return {
                "error": "无推荐产品，无法进行合规检查",
                "current_agent": "compliance",
            }
        
        # Transform to ComplianceState
        compliance_input = transform_to_compliance_state(state)
        
        # Create and invoke Compliance Subgraph
        compliance_subgraph = create_compliance_subgraph()
        
        logger.debug("Invoking Compliance Subgraph...")
        result = await compliance_subgraph.ainvoke(compliance_input)
        
        # Transform results back to MainState
        result_updates = transform_from_compliance_state(state, result)
        updates.update(result_updates)
        
        logger.info(
            f"Compliance Subgraph complete: "
            f"compliance_passed={result.get('compliance_passed')}, "
            f"{len(result.get('filtered_recommendations', []))} products passed"
        )
        
        return updates
        
    except Exception as e:
        logger.error(f"Error in compliance_node: {e}")
        return {
            "error": f"合规检查失败: {str(e)}",
            "current_agent": "compliance",
        }


# ==================== Routing Functions ====================

def should_continue_to_recommendation(state: MainState) -> str:
    """
    Determine if we should proceed to recommendation or end
    
    Routes based on:
    - profile_complete: If True, proceed to recommendation
    - error: If error exists, end with error status
    
    Args:
        state: Current MainState
        
    Returns:
        Next node name or END
    """
    # Check for errors
    if state.get("error"):
        logger.warning(f"Error in state: {state.get('error')}")
        return END
    
    # Check if profile is complete
    if state.get("profile_complete"):
        logger.info("Profile complete, proceeding to recommendation")
        return "recommendation"
    
    # Profile not complete - end (will continue in next turn)
    logger.info("Profile not complete, ending for now")
    return END


def should_continue_to_compliance(state: MainState) -> str:
    """
    Determine if we should proceed to compliance or end
    
    Routes based on:
    - recommendation_generated: If True, proceed to compliance
    - error: If error exists, end with error status
    
    Args:
        state: Current MainState
        
    Returns:
        Next node name or END
    """
    # Check for errors
    if state.get("error"):
        logger.warning(f"Error in state: {state.get('error')}")
        return END
    
    # Check if recommendations were generated
    if state.get("recommendation_generated") and state.get("recommendations"):
        logger.info("Recommendations generated, proceeding to compliance")
        return "compliance"
    
    # No recommendations - end
    logger.info("No recommendations generated, ending")
    return END


def should_end(state: MainState) -> str:
    """
    Determine final status before ending
    
    Sets the final status based on the state.
    
    Args:
        state: Current MainState
        
    Returns:
        Always returns END
    """
    # Determine final status
    if state.get("error"):
        status = "error"
    elif state.get("compliance_passed") and state.get("recommendations"):
        status = "completed"
    else:
        status = "active"
    
    logger.info(f"Main Graph execution complete with status: {status}")
    
    return END


# ==================== Main Graph Builder ====================

def create_main_graph(
    store=None,
    checkpointer: Optional[PostgresSaver] = None
) -> StateGraph:
    """
    Create the Main Graph (Orchestrator)
    
    The main graph orchestrates the three subgraphs in sequence:
    START → profile → recommendation → compliance → END
    
    Each node:
    1. Transforms MainState to subgraph-specific state
    2. Invokes the subgraph
    3. Transforms results back to MainState
    
    Args:
        store: Optional PostgresStore instance (for dependency injection)
        checkpointer: Optional PostgresSaver instance for session persistence
        
    Returns:
        Compiled StateGraph for Main Graph
    """
    logger.info("Creating Main Graph (Orchestrator)")
    
    # Create the graph with MainState
    builder = StateGraph(MainState)
    
    # Add nodes
    builder.add_node("profile", profile_node)
    builder.add_node("recommendation", recommendation_node)
    builder.add_node("compliance", compliance_node)
    
    # Add edges
    # START → profile
    builder.add_edge(START, "profile")
    
    # profile → recommendation (conditional)
    builder.add_conditional_edges(
        "profile",
        should_continue_to_recommendation,
        {
            "recommendation": "recommendation",
            END: END,
        }
    )
    
    # recommendation → compliance (conditional)
    builder.add_conditional_edges(
        "recommendation",
        should_continue_to_compliance,
        {
            "compliance": "compliance",
            END: END,
        }
    )
    
    # compliance → END
    builder.add_edge("compliance", END)
    
    # Compile the graph
    # Note: Checkpointer is passed during compilation
    if checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        logger.info("Main Graph compiled with checkpointer")
    else:
        graph = builder.compile()
        logger.info("Main Graph compiled without checkpointer")
    
    logger.info("Main Graph (Orchestrator) created successfully")
    
    return graph


def create_main_graph_with_checkpointer(
    store=None,
    connection_string: Optional[str] = None
) -> StateGraph:
    """
    Create the Main Graph with PostgresSaver checkpointer
    
    This is a convenience function that:
    1. Gets the PostgresSaver checkpointer
    2. Creates the Main Graph with the checkpointer
    
    Args:
        store: Optional PostgresStore instance
        connection_string: Optional database connection string
        
    Returns:
        Compiled StateGraph with checkpointer configured
    """
    logger.info("Creating Main Graph with checkpointer")
    
    # Get checkpointer
    checkpointer = get_checkpointer(
        connection_string=connection_string,
        auto_setup=True,
    )
    
    # Create and return graph
    return create_main_graph(store=store, checkpointer=checkpointer)


# ==================== Convenience Functions ====================

async def run_main_graph(
    session_id: str,
    user_id: str,
    messages: List[Any],
    user_profile: Optional[UserProfile] = None,
    existing_slots: Optional[Dict[str, Any]] = None,
    checkpointer: Optional[PostgresSaver] = None,
    thread_id: Optional[str] = None,
) -> MainState:
    """
    Convenience function to run the Main Graph
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        messages: List of conversation messages
        user_profile: Optional existing user profile
        existing_slots: Optional existing slots
        checkpointer: Optional PostgresSaver for session persistence
        thread_id: Optional thread ID for checkpointer (defaults to session_id)
        
    Returns:
        Final MainState after graph execution
    """
    # Create initial state
    initial_state = create_initial_main_state(
        session_id=session_id,
        user_id=user_id,
    )
    
    # Override with provided values
    initial_state["messages"] = messages
    if user_profile:
        initial_state["user_profile"] = user_profile
        initial_state["profile_complete"] = True
    if existing_slots:
        initial_state["slots"] = existing_slots
    
    # Create graph
    graph = create_main_graph(checkpointer=checkpointer)
    
    # Prepare config for checkpointer
    config = {}
    if checkpointer and thread_id:
        config["configurable"] = {"thread_id": thread_id or session_id}
    
    # Run graph
    if config:
        result = await graph.ainvoke(initial_state, config)
    else:
        result = await graph.ainvoke(initial_state)
    
    return result


async def process_user_message(
    session_id: str,
    user_id: str,
    user_message: str,
    checkpointer: Optional[PostgresSaver] = None,
) -> MainState:
    """
    Process a single user message through the Main Graph
    
    This is the primary entry point for handling user messages.
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        user_message: User's message text
        checkpointer: Optional PostgresSaver for session persistence
        
    Returns:
        Final MainState after processing
    """
    from langchain_core.messages import HumanMessage
    
    # Create message
    messages = [HumanMessage(content=user_message)]
    
    # Run graph
    return await run_main_graph(
        session_id=session_id,
        user_id=user_id,
        messages=messages,
        checkpointer=checkpointer,
        thread_id=session_id,
    )


# ==================== Module Exports ====================

__all__ = [
    # Main graph builders
    "create_main_graph",
    "create_main_graph_with_checkpointer",
    
    # Convenience functions
    "run_main_graph",
    "process_user_message",
    
    # State transformation functions
    "transform_to_profile_state",
    "transform_from_profile_state",
    "transform_to_recommendation_state",
    "transform_from_recommendation_state",
    "transform_to_compliance_state",
    "transform_from_compliance_state",
    
    # Node functions
    "profile_node",
    "recommendation_node",
    "compliance_node",
    
    # Constants
    "AGENT_ORDER",
    "MAX_RETRY_ATTEMPTS",
]
