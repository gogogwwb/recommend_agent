"""
Unit tests for Main Graph (Orchestrator)

Tests the main graph orchestration of Profile, Recommendation, and Compliance subgraphs.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import END

from agents.main_graph import (
    create_main_graph,
    create_main_graph_with_checkpointer,
    run_main_graph,
    process_user_message,
    profile_node,
    recommendation_node,
    compliance_node,
    transform_to_profile_state,
    transform_from_profile_state,
    transform_to_recommendation_state,
    transform_from_recommendation_state,
    transform_to_compliance_state,
    transform_from_compliance_state,
    AGENT_ORDER,
    MAX_RETRY_ATTEMPTS,
)
from models.subgraph_states import (
    MainState,
    ProfileState,
    RecommendationState,
    ComplianceState,
    create_initial_main_state,
)
from models.user import UserProfile, MaritalStatus, IncomeRange, RiskPreference
from models.product import Product, RecommendationResult, PremiumRange, AgeRange


# ==================== Fixtures ====================

@pytest.fixture
def sample_user_profile():
    """Create a sample user profile for testing"""
    return UserProfile(
        age=35,
        occupation="工程师",
        marital_status=MaritalStatus.MARRIED,
        has_children=True,
        children_count=1,
        has_dependents=True,
        dependents_count=2,
        family_size=3,
        income_range=IncomeRange.MEDIUM,
        risk_preference=RiskPreference.BALANCED,
    )


@pytest.fixture
def sample_product():
    """Create a sample product for testing"""
    return Product(
        product_id="test-product-001",
        product_name="测试重疾险",
        product_type="critical_illness",
        provider="测试保险公司",
        coverage_scope=["重大疾病", "轻症"],
        premium_range=PremiumRange(min_premium=5000, max_premium=10000),
        age_range=AgeRange(min_age=18, max_age=60),
        payment_period=["20年"],
        coverage_period=["终身"],
        features=["120种重疾保障"],
        advantages=["保障全面"],
        suitable_for=["家庭支柱"],
        is_available=True,
    )


@pytest.fixture
def sample_recommendation(sample_product):
    """Create a sample recommendation for testing"""
    return RecommendationResult(
        product=sample_product,
        rank=1,
        match_score=85.0,
        confidence_score=0.85,
        explanation="适合您的需求",
        match_dimensions={"age_match": 90.0, "income_match": 80.0},
        why_suitable=["年龄符合", "保费合适"],
        key_benefits=["保障全面"],
        compliance_passed=False,
        compliance_issues=[],
    )


@pytest.fixture
def sample_main_state(sample_user_profile):
    """Create a sample main state for testing"""
    return MainState(
        messages=[HumanMessage(content="我想买保险")],
        user_id="test-user-001",
        session_id="test-session-001",
        user_profile=sample_user_profile,
        profile_complete=True,
        risk_preference="balanced",
        risk_score=50.0,
        existing_coverage=[],
        recommendations=[],
        recommendation_generated=False,
        coverage_gap=None,
        compliance_checks=[],
        compliance_passed=False,
        disclosure_info=[],
        current_intent="request_recommendation",
        slots={"age": 35, "occupation": "工程师"},
        missing_slots=[],
        next_agent=None,
        current_agent=None,
        error=None,
        status="active",
        background_mode=False,
        saved_progress=None,
        user_feedback=None,
        feedback_reason=None,
        profile_change_history=[],
        recommendation_constraints=None,
        excluded_products=[],
    )


# ==================== Test State Transformations ====================

class TestStateTransformations:
    """Tests for state transformation functions"""
    
    def test_transform_to_profile_state(self, sample_main_state):
        """Test transforming MainState to ProfileState"""
        profile_state = transform_to_profile_state(sample_main_state)
        
        assert isinstance(profile_state, dict)
        assert profile_state["user_id"] == "test-user-001"
        assert profile_state["session_id"] == "test-session-001"
        assert len(profile_state["messages"]) == 1
        assert profile_state["profile_complete"] == True
        assert profile_state["slots"]["age"] == 35
    
    def test_transform_from_profile_state(self, sample_main_state):
        """Test transforming ProfileState result back to MainState"""
        profile_result = ProfileState(
            messages=[],
            user_id="test-user-001",
            session_id="test-session-001",
            user_profile=sample_main_state["user_profile"],
            slots={"age": 35, "occupation": "工程师", "income_range": "medium"},
            missing_slots=[],
            risk_preference="balanced",
            risk_score=50.0,
            existing_coverage=[],
            current_intent="request_recommendation",
            profile_complete=True,
            error=None,
        )
        
        updates = transform_from_profile_state(sample_main_state, profile_result)
        
        assert updates["profile_complete"] == True
        assert updates["slots"]["income_range"] == "medium"
        assert updates["risk_preference"] == "balanced"
    
    def test_transform_to_recommendation_state(self, sample_main_state):
        """Test transforming MainState to RecommendationState"""
        rec_state = transform_to_recommendation_state(sample_main_state)
        
        assert isinstance(rec_state, dict)
        assert rec_state["user_id"] == "test-user-001"
        assert rec_state["session_id"] == "test-session-001"
        assert rec_state["user_profile"] is not None
        assert rec_state["risk_preference"] == "balanced"
    
    def test_transform_from_recommendation_state(
        self, sample_main_state, sample_recommendation
    ):
        """Test transforming RecommendationState result back to MainState"""
        rec_result = RecommendationState(
            user_id="test-user-001",
            session_id="test-session-001",
            user_profile=sample_main_state["user_profile"],
            risk_preference="balanced",
            risk_score=50.0,
            existing_coverage=[],
            recommendations=[sample_recommendation],
            explanations=["适合您的需求"],
            coverage_gap={"critical_illness": 500000},
            recommendation_constraints=None,
            excluded_products=[],
            recommendation_generated=True,
            error=None,
        )
        
        updates = transform_from_recommendation_state(sample_main_state, rec_result)
        
        assert updates["recommendation_generated"] == True
        assert len(updates["recommendations"]) == 1
        assert updates["coverage_gap"]["critical_illness"] == 500000
    
    def test_transform_to_compliance_state(
        self, sample_main_state, sample_recommendation
    ):
        """Test transforming MainState to ComplianceState"""
        sample_main_state["recommendations"] = [sample_recommendation]
        
        compliance_state = transform_to_compliance_state(sample_main_state)
        
        assert isinstance(compliance_state, dict)
        assert compliance_state["user_id"] == "test-user-001"
        assert compliance_state["session_id"] == "test-session-001"
        assert len(compliance_state["recommendations"]) == 1
    
    def test_transform_from_compliance_state(
        self, sample_main_state, sample_recommendation
    ):
        """Test transforming ComplianceState result back to MainState"""
        sample_recommendation.compliance_passed = True
        
        compliance_result = ComplianceState(
            user_id="test-user-001",
            session_id="test-session-001",
            user_profile=sample_main_state["user_profile"],
            recommendations=[sample_recommendation],
            compliance_checks=[],
            compliance_passed=True,
            disclosure_info=[],
            filtered_recommendations=[sample_recommendation],
            error=None,
        )
        
        updates = transform_from_compliance_state(sample_main_state, compliance_result)
        
        assert updates["compliance_passed"] == True
        assert len(updates["recommendations"]) == 1


# ==================== Test Graph Creation ====================

class TestGraphCreation:
    """Tests for graph creation functions"""
    
    def test_create_main_graph(self):
        """Test creating main graph without checkpointer"""
        graph = create_main_graph()
        
        assert graph is not None
        assert hasattr(graph, 'ainvoke')
        assert hasattr(graph, 'ainvoke')
    
    def test_create_main_graph_with_checkpointer(self):
        """Test creating main graph with checkpointer"""
        from langgraph.checkpoint.memory import InMemorySaver
        
        with patch('agents.main_graph.get_checkpointer') as mock_get_checkpointer:
            # Use InMemorySaver instead of MagicMock for a valid checkpointer
            mock_checkpointer = InMemorySaver()
            mock_get_checkpointer.return_value = mock_checkpointer
            
            graph = create_main_graph_with_checkpointer()
            
            assert graph is not None
            mock_get_checkpointer.assert_called_once()
    
    def test_agent_order_constant(self):
        """Test AGENT_ORDER constant"""
        assert AGENT_ORDER == ["profile", "recommendation", "compliance"]
    
    def test_max_retry_attempts_constant(self):
        """Test MAX_RETRY_ATTEMPTS constant"""
        assert MAX_RETRY_ATTEMPTS == 2


# ==================== Test Node Functions ====================

class TestNodeFunctions:
    """Tests for node functions"""
    
    @pytest.mark.asyncio
    async def test_profile_node_profile_complete(self, sample_main_state):
        """Test profile node when profile is already complete"""
        result = await profile_node(sample_main_state)
        
        assert result["current_agent"] == "profile"
        # Should skip subgraph execution
    
    @pytest.mark.asyncio
    async def test_profile_node_profile_incomplete(self, sample_main_state):
        """Test profile node when profile is incomplete"""
        sample_main_state["profile_complete"] = False
        sample_main_state["user_profile"] = None
        
        with patch('agents.main_graph.create_profile_subgraph') as mock_create:
            mock_subgraph = AsyncMock()
            mock_subgraph.ainvoke.return_value = {
                "profile_complete": True,
                "user_profile": sample_main_state["user_profile"],
                "slots": {"age": 35},
                "missing_slots": [],
                "error": None,
            }
            mock_create.return_value = mock_subgraph
            
            result = await profile_node(sample_main_state)
            
            assert result["current_agent"] == "profile"
            mock_subgraph.ainvoke.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_recommendation_node_profile_incomplete(self, sample_main_state):
        """Test recommendation node when profile is incomplete"""
        sample_main_state["profile_complete"] = False
        
        result = await recommendation_node(sample_main_state)
        
        assert result["current_agent"] == "recommendation"
        assert result["error"] is not None
    
    @pytest.mark.asyncio
    async def test_recommendation_node_already_generated(self, sample_main_state):
        """Test recommendation node when recommendations already generated"""
        sample_main_state["recommendation_generated"] = True
        
        result = await recommendation_node(sample_main_state)
        
        assert result["current_agent"] == "recommendation"
    
    @pytest.mark.asyncio
    async def test_compliance_node_no_recommendations(self, sample_main_state):
        """Test compliance node when no recommendations exist"""
        sample_main_state["recommendations"] = []
        
        result = await compliance_node(sample_main_state)
        
        assert result["current_agent"] == "compliance"
        assert result["error"] is not None


# ==================== Test Convenience Functions ====================

class TestConvenienceFunctions:
    """Tests for convenience functions"""
    
    @pytest.mark.asyncio
    async def test_run_main_graph(self, sample_user_profile):
        """Test run_main_graph function"""
        with patch('agents.main_graph.create_main_graph') as mock_create:
            mock_graph = AsyncMock()
            mock_graph.ainvoke.return_value = create_initial_main_state(
                session_id="test-session",
                user_id="test-user"
            )
            mock_create.return_value = mock_graph
            
            result = await run_main_graph(
                session_id="test-session",
                user_id="test-user",
                messages=[HumanMessage(content="我想买保险")],
            )
            
            assert result is not None
            mock_graph.ainvoke.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_user_message(self):
        """Test process_user_message function"""
        with patch('agents.main_graph.run_main_graph') as mock_run:
            mock_run.return_value = create_initial_main_state(
                session_id="test-session",
                user_id="test-user"
            )
            
            result = await process_user_message(
                session_id="test-session",
                user_id="test-user",
                user_message="我想买保险",
            )
            
            assert result is not None
            mock_run.assert_called_once()


# ==================== Test Error Handling ====================

class TestErrorHandling:
    """Tests for error handling"""
    
    @pytest.mark.asyncio
    async def test_profile_node_error_handling(self, sample_main_state):
        """Test profile node error handling"""
        sample_main_state["profile_complete"] = False
        
        with patch('agents.main_graph.create_profile_subgraph') as mock_create:
            mock_subgraph = AsyncMock()
            mock_subgraph.ainvoke.side_effect = Exception("Test error")
            mock_create.return_value = mock_subgraph
            
            result = await profile_node(sample_main_state)
            
            assert result["error"] is not None
            assert "画像收集失败" in result["error"]
    
    @pytest.mark.asyncio
    async def test_recommendation_node_error_handling(self, sample_main_state):
        """Test recommendation node error handling"""
        with patch('agents.main_graph.create_recommendation_subgraph') as mock_create:
            mock_subgraph = AsyncMock()
            mock_subgraph.ainvoke.side_effect = Exception("Test error")
            mock_create.return_value = mock_subgraph
            
            result = await recommendation_node(sample_main_state)
            
            assert result["error"] is not None
            assert "推荐生成失败" in result["error"]
    
    @pytest.mark.asyncio
    async def test_compliance_node_error_handling(
        self, sample_main_state, sample_recommendation
    ):
        """Test compliance node error handling"""
        sample_main_state["recommendations"] = [sample_recommendation]
        
        with patch('agents.main_graph.create_compliance_subgraph') as mock_create:
            mock_subgraph = AsyncMock()
            mock_subgraph.ainvoke.side_effect = Exception("Test error")
            mock_create.return_value = mock_subgraph
            
            result = await compliance_node(sample_main_state)
            
            assert result["error"] is not None
            assert "合规检查失败" in result["error"]


# ==================== Test Routing Functions ====================

class TestRoutingFunctions:
    """Tests for routing functions"""
    
    def test_should_continue_to_recommendation_with_error(self, sample_main_state):
        """Test routing when there's an error"""
        sample_main_state["error"] = "Test error"
        
        from agents.main_graph import should_continue_to_recommendation
        result = should_continue_to_recommendation(sample_main_state)
        
        assert result == END
    
    def test_should_continue_to_recommendation_profile_complete(self, sample_main_state):
        """Test routing when profile is complete"""
        from agents.main_graph import should_continue_to_recommendation
        result = should_continue_to_recommendation(sample_main_state)
        
        assert result == "recommendation"
    
    def test_should_continue_to_recommendation_profile_incomplete(self, sample_main_state):
        """Test routing when profile is incomplete"""
        sample_main_state["profile_complete"] = False
        
        from agents.main_graph import should_continue_to_recommendation
        result = should_continue_to_recommendation(sample_main_state)
        
        assert result == END
    
    def test_should_continue_to_compliance_with_error(self, sample_main_state):
        """Test routing when there's an error"""
        sample_main_state["error"] = "Test error"
        
        from agents.main_graph import should_continue_to_compliance
        result = should_continue_to_compliance(sample_main_state)
        
        assert result == END
    
    def test_should_continue_to_compliance_with_recommendations(
        self, sample_main_state, sample_recommendation
    ):
        """Test routing when recommendations exist"""
        sample_main_state["recommendation_generated"] = True
        sample_main_state["recommendations"] = [sample_recommendation]
        
        from agents.main_graph import should_continue_to_compliance
        result = should_continue_to_compliance(sample_main_state)
        
        assert result == "compliance"
    
    def test_should_continue_to_compliance_no_recommendations(self, sample_main_state):
        """Test routing when no recommendations"""
        sample_main_state["recommendation_generated"] = False
        sample_main_state["recommendations"] = []
        
        from agents.main_graph import should_continue_to_compliance
        result = should_continue_to_compliance(sample_main_state)
        
        assert result == END


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
