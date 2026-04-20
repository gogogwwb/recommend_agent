"""
Unit tests for Profile Collection Subgraph

Tests the core functionality of the Profile Subgraph:
- Slot extraction from conversation
- Profile validation
- Store API integration
- Subgraph flow and state transitions
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage

from agents.profile_subgraph import (
    create_profile_subgraph,
    extract_slots_node,
    validate_profile_node,
    store_slots_node,
    REQUIRED_SLOTS,
    OPTIONAL_SLOTS,
    INTENT_TYPES,
)
from models.subgraph_states import ProfileState
from models.user import UserProfile, MaritalStatus, IncomeRange, RiskPreference


# ==================== Fixtures ====================

@pytest.fixture
def mock_llm():
    """Mock LLM for testing"""
    mock = AsyncMock()
    mock.ainvoke = AsyncMock()
    return mock


@pytest.fixture
def mock_store_manager():
    """Mock Store Manager for testing"""
    mock = Mock()
    mock.update_user_profile = Mock()
    mock.get_user_profile = Mock(return_value=None)
    return mock


@pytest.fixture
def initial_profile_state():
    """Create initial ProfileState for testing"""
    return ProfileState(
        messages=[HumanMessage(content="你好，我今年30岁")],
        user_id="test_user_123",
        session_id="test_session_456",
        user_profile=None,
        slots={},
        missing_slots=REQUIRED_SLOTS.copy(),
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent=None,
        profile_complete=False,
        error=None
    )


# ==================== Test Constants ====================

def test_required_slots():
    """Test that required slots are defined correctly"""
    assert "age" in REQUIRED_SLOTS
    assert "occupation" in REQUIRED_SLOTS
    assert "marital_status" in REQUIRED_SLOTS
    assert "income_range" in REQUIRED_SLOTS
    assert len(REQUIRED_SLOTS) == 4


def test_optional_slots():
    """Test that optional slots are defined correctly"""
    assert "risk_preference" in OPTIONAL_SLOTS
    assert "health_status" in OPTIONAL_SLOTS
    assert "has_children" in OPTIONAL_SLOTS


def test_intent_types():
    """Test that intent types are defined correctly"""
    assert "provide_info" in INTENT_TYPES
    assert "chitchat" in INTENT_TYPES
    assert "modify_info" in INTENT_TYPES
    assert len(INTENT_TYPES) >= 8


# ==================== Test Node Functions ====================

@pytest.mark.asyncio
async def test_extract_slots_node_basic(initial_profile_state, mock_llm):
    """Test basic slot extraction"""
    # Mock LLM response
    mock_llm.ainvoke.return_value = Mock(content='''
    {
        "intent": "provide_info",
        "slots": {
            "age": 30
        },
        "response": "好的，我已记录您的年龄是30岁。"
    }
    ''')
    
    with patch('agents.profile_subgraph._get_llm', return_value=mock_llm):
        result = await extract_slots_node(initial_profile_state)
    
    assert result["current_intent"] == "provide_info"
    assert "age" in result["slots"]
    assert result["slots"]["age"] == 30
    assert result["error"] is None


@pytest.mark.asyncio
async def test_extract_slots_node_chitchat(initial_profile_state, mock_llm):
    """Test handling of chitchat intent"""
    # Update state with chitchat message
    initial_profile_state["messages"] = [HumanMessage(content="今天天气怎么样？")]
    
    # Mock LLM response
    mock_llm.ainvoke.return_value = Mock(content='''
    {
        "intent": "chitchat",
        "slots": {},
        "response": "我是保险推荐助手，主要帮助您了解保险产品。请问您想了解哪方面的保险？"
    }
    ''')
    
    with patch('agents.profile_subgraph._get_llm', return_value=mock_llm):
        result = await extract_slots_node(initial_profile_state)
    
    assert result["current_intent"] == "chitchat"
    assert result["error"] is None


@pytest.mark.asyncio
async def test_validate_profile_node_complete():
    """Test profile validation with complete data"""
    state = ProfileState(
        messages=[],
        user_id="test_user",
        session_id="test_session",
        user_profile=None,
        slots={
            "age": 30,
            "occupation": "软件工程师",
            "marital_status": "married",
            "income_range": "medium_high",
            "risk_preference": "balanced"
        },
        missing_slots=[],
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent="provide_info",
        profile_complete=False,
        error=None
    )
    
    result = await validate_profile_node(state)
    
    assert result["profile_complete"] is True
    assert result["user_profile"] is not None
    assert isinstance(result["user_profile"], UserProfile)
    assert result["error"] is None


@pytest.mark.asyncio
async def test_validate_profile_node_incomplete():
    """Test profile validation with incomplete data"""
    state = ProfileState(
        messages=[],
        user_id="test_user",
        session_id="test_session",
        user_profile=None,
        slots={
            "age": 30,
            "occupation": "软件工程师"
        },
        missing_slots=["marital_status", "income_range"],
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent="provide_info",
        profile_complete=False,
        error=None
    )
    
    result = await validate_profile_node(state)
    
    assert result["profile_complete"] is False
    assert result["user_profile"] is None


@pytest.mark.asyncio
async def test_validate_profile_node_invalid_age():
    """Test profile validation with invalid age"""
    state = ProfileState(
        messages=[],
        user_id="test_user",
        session_id="test_session",
        user_profile=None,
        slots={
            "age": 150,  # Invalid age
            "occupation": "软件工程师",
            "marital_status": "married",
            "income_range": "medium_high"
        },
        missing_slots=[],
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent="provide_info",
        profile_complete=False,
        error=None
    )
    
    result = await validate_profile_node(state)
    
    assert result["profile_complete"] is False
    assert result["error"] is not None
    assert "年龄" in result["error"]


@pytest.mark.asyncio
async def test_store_slots_node_success(mock_store_manager):
    """Test successful slot storage to Store API"""
    state = ProfileState(
        messages=[],
        user_id="test_user_123",
        session_id="test_session",
        user_profile=None,
        slots={
            "age": 30,
            "occupation": "软件工程师"
        },
        missing_slots=[],
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent="provide_info",
        profile_complete=False,
        error=None
    )
    
    with patch('agents.profile_subgraph.get_store_manager', return_value=mock_store_manager):
        result = await store_slots_node(state)
    
    assert result["error"] is None
    mock_store_manager.update_user_profile.assert_called_once()


@pytest.mark.asyncio
async def test_store_slots_node_no_user_id():
    """Test slot storage when user_id is missing"""
    state = ProfileState(
        messages=[],
        user_id="",  # Empty user_id
        session_id="test_session",
        user_profile=None,
        slots={"age": 30},
        missing_slots=[],
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent="provide_info",
        profile_complete=False,
        error=None
    )
    
    result = await store_slots_node(state)
    
    # Should not fail, just skip storage
    assert result["error"] is None


# ==================== Test Subgraph Creation ====================

def test_create_profile_subgraph():
    """Test that Profile Subgraph can be created"""
    subgraph = create_profile_subgraph()
    
    assert subgraph is not None
    # Verify the graph has the expected nodes
    # Note: The actual node names might differ based on LangGraph implementation
    assert hasattr(subgraph, 'nodes') or hasattr(subgraph, 'graph')


def test_create_profile_subgraph_with_injected_skill():
    """Test that Profile Subgraph accepts injected InsuranceDomainSkill
    
    Requirements: 5.1, 5.3, 5.6
    """
    from skills.insurance_domain import InsuranceDomainSkill
    
    # Create a mock skill
    mock_skill = Mock(spec=InsuranceDomainSkill)
    
    # Create subgraph with injected skill - should NOT create default
    subgraph = create_profile_subgraph(insurance_skill=mock_skill)
    
    assert subgraph is not None
    # The subgraph should be created successfully with the injected skill


def test_create_profile_subgraph_creates_default_skill():
    """Test that Profile Subgraph creates default InsuranceDomainSkill when not provided
    
    Requirements: 5.3
    """
    # Create subgraph without providing a skill - should create default
    subgraph = create_profile_subgraph(insurance_skill=None)
    
    assert subgraph is not None
    # The subgraph should be created successfully with a default skill


def test_create_profile_subgraph_default_parameter():
    """Test that Profile Subgraph works with default parameter (no args)
    
    Requirements: 5.3
    """
    # Create subgraph with no arguments - should create default skill
    subgraph = create_profile_subgraph()
    
    assert subgraph is not None


# ==================== Test State Transitions ====================

@pytest.mark.asyncio
async def test_profile_subgraph_flow_complete(mock_llm, mock_store_manager):
    """Test complete Profile Subgraph flow"""
    # Create initial state
    initial_state = ProfileState(
        messages=[HumanMessage(content="我今年30岁，职业是软件工程师，已婚，收入中等偏上")],
        user_id="test_user_123",
        session_id="test_session_456",
        user_profile=None,
        slots={},
        missing_slots=REQUIRED_SLOTS.copy(),
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent=None,
        profile_complete=False,
        error=None
    )
    
    # Mock LLM to extract all slots
    mock_llm.ainvoke.return_value = Mock(content='''
    {
        "intent": "provide_info",
        "slots": {
            "age": 30,
            "occupation": "软件工程师",
            "marital_status": "married",
            "income_range": "medium_high"
        },
        "response": "好的，我已记录您的信息。"
    }
    ''')
    
    with patch('agents.profile_subgraph._get_llm', return_value=mock_llm):
        with patch('agents.profile_subgraph.get_store_manager', return_value=mock_store_manager):
            # Create and run subgraph
            subgraph = create_profile_subgraph()
            result = await subgraph.ainvoke(initial_state)
    
    # Verify final state
    assert result["profile_complete"] is True
    assert result["user_profile"] is not None
    assert isinstance(result["user_profile"], UserProfile)


# ==================== Test Edge Cases ====================

@pytest.mark.asyncio
async def test_extract_slots_node_empty_messages():
    """Test slot extraction with empty messages"""
    state = ProfileState(
        messages=[],  # Empty messages
        user_id="test_user",
        session_id="test_session",
        user_profile=None,
        slots={},
        missing_slots=REQUIRED_SLOTS.copy(),
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent=None,
        profile_complete=False,
        error=None
    )
    
    result = await extract_slots_node(state)
    
    assert result["current_intent"] == "unknown"


@pytest.mark.asyncio
async def test_validate_profile_node_with_children():
    """Test profile validation with children information"""
    state = ProfileState(
        messages=[],
        user_id="test_user",
        session_id="test_session",
        user_profile=None,
        slots={
            "age": 35,
            "occupation": "产品经理",
            "marital_status": "married",
            "income_range": "high",
            "has_children": True,
            "children_count": 2,
            "family_size": 4
        },
        missing_slots=[],
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent="provide_info",
        profile_complete=False,
        error=None
    )
    
    result = await validate_profile_node(state)
    
    assert result["profile_complete"] is True
    assert result["user_profile"].has_children is True
    assert result["user_profile"].children_count == 2
    assert result["user_profile"].family_size == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
