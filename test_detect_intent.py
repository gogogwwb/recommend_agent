"""Quick test for detect_intent_node implementation"""
import asyncio
from langchain_core.messages import HumanMessage
from agents.profile_subgraph import detect_intent_node
from models.subgraph_states import ProfileState


async def test_detect_intent_terminology():
    """Test terminology question detection"""
    state = ProfileState(
        messages=[HumanMessage(content="什么是重疾险？")],
        user_id="test_user",
        session_id="test_session",
        user_profile=None,
        slots={},
        missing_slots=[],
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent=None,
        question_type=None,
        extracted_entities={},
        profile_complete=False,
        error=None
    )
    
    result = await detect_intent_node(state)
    
    print("Test: Terminology Question")
    print(f"  Intent: {result['current_intent']}")
    print(f"  Question Type: {result['question_type']}")
    print(f"  Entities: {result['extracted_entities']}")
    assert result['current_intent'] == 'ask_question', f"Expected 'ask_question', got {result['current_intent']}"
    assert result['question_type'] == 'terminology', f"Expected 'terminology', got {result['question_type']}"
    assert result['extracted_entities'].get('term') == '重疾险', f"Expected '重疾险', got {result['extracted_entities'].get('term')}"
    print("  ✓ PASSED\n")


async def test_detect_intent_comparison():
    """Test comparison question detection"""
    state = ProfileState(
        messages=[HumanMessage(content="重疾险和医疗险有什么区别？")],
        user_id="test_user",
        session_id="test_session",
        user_profile=None,
        slots={},
        missing_slots=[],
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent=None,
        question_type=None,
        extracted_entities={},
        profile_complete=False,
        error=None
    )
    
    result = await detect_intent_node(state)
    
    print("Test: Comparison Question")
    print(f"  Intent: {result['current_intent']}")
    print(f"  Question Type: {result['question_type']}")
    print(f"  Entities: {result['extracted_entities']}")
    assert result['current_intent'] == 'ask_question', f"Expected 'ask_question', got {result['current_intent']}"
    assert result['question_type'] == 'comparison', f"Expected 'comparison', got {result['question_type']}"
    assert 'product_types' in result['extracted_entities'], "Expected 'product_types' in entities"
    print("  ✓ PASSED\n")


async def test_detect_intent_claim():
    """Test claim process question detection"""
    state = ProfileState(
        messages=[HumanMessage(content="怎么理赔？")],
        user_id="test_user",
        session_id="test_session",
        user_profile=None,
        slots={},
        missing_slots=[],
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent=None,
        question_type=None,
        extracted_entities={},
        profile_complete=False,
        error=None
    )
    
    result = await detect_intent_node(state)
    
    print("Test: Claim Process Question")
    print(f"  Intent: {result['current_intent']}")
    print(f"  Question Type: {result['question_type']}")
    print(f"  Entities: {result['extracted_entities']}")
    assert result['current_intent'] == 'ask_question', f"Expected 'ask_question', got {result['current_intent']}"
    assert result['question_type'] == 'claim', f"Expected 'claim', got {result['question_type']}"
    print("  ✓ PASSED\n")


async def test_detect_intent_provide_info():
    """Test provide_info intent detection"""
    state = ProfileState(
        messages=[HumanMessage(content="我今年30岁，是一名工程师")],
        user_id="test_user",
        session_id="test_session",
        user_profile=None,
        slots={},
        missing_slots=[],
        risk_preference=None,
        risk_score=None,
        existing_coverage=[],
        current_intent=None,
        question_type=None,
        extracted_entities={},
        profile_complete=False,
        error=None
    )
    
    result = await detect_intent_node(state)
    
    print("Test: Provide Info (Not a Question)")
    print(f"  Intent: {result['current_intent']}")
    print(f"  Question Type: {result['question_type']}")
    print(f"  Entities: {result['extracted_entities']}")
    assert result['current_intent'] == 'provide_info', f"Expected 'provide_info', got {result['current_intent']}"
    assert result['question_type'] is None, f"Expected None, got {result['question_type']}"
    print("  ✓ PASSED\n")


async def main():
    print("=" * 60)
    print("Testing detect_intent_node Implementation")
    print("=" * 60 + "\n")
    
    await test_detect_intent_terminology()
    await test_detect_intent_comparison()
    await test_detect_intent_claim()
    await test_detect_intent_provide_info()
    
    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
