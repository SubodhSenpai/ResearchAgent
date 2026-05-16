from langgraph.graph import StateGraph, END
from graph.state import ResearchState
from agents.supervisor import SupervisorAgent
from agents.researcher import ResearchAgent
from agents.analyst import AnalystAgent
from agents.critic import CriticAgent
from agents.writer import WriterAgent
from agents.validator import ValidatorAgent
from memory.session_memory import SessionMemory
import logging

logger = logging.getLogger(__name__)

def build_research_graph():
    '''Build and return the compiled LangGraph research agent with deep research capabilities.'''

    # Agent instantiation
    supervisor = SupervisorAgent()
    researcher = ResearchAgent()
    analyst = AnalystAgent()
    critic = CriticAgent()
    writer = WriterAgent()
    validator = ValidatorAgent()
    memory = SessionMemory()

    def memory_check_node(state: ResearchState) -> ResearchState:
        '''Short-circuit the graph if a cached answer exists for this user.'''
        session_id = state['session_id']
        user_id = state['user_id']

        if state.get('interrupt_requested'):
            logger.warning(f"Session {session_id} interrupted before execution")
            return {**state, 'final_answer': '[Interrupted by user]', 'error': 'User interrupted execution'}

        # Check cache for this specific user
        cached = memory.is_cache_hit(state['query'], user_id=user_id)
        if cached:
            logger.info(f"Cache hit for user {user_id}, query: {state['query'][:50]}...")
            return {**state, 'final_answer': cached}

        # Initialize new state fields
        return {
            **state,
            'sub_queries': state.get('sub_queries', []),
            'source_urls': state.get('source_urls', []),
            'research_gaps': state.get('research_gaps', []),
        }

    def save_to_memory(state: ResearchState) -> ResearchState:
        '''Persist the final answer with full session context.'''
        if state.get('final_answer') and not state.get('interrupt_requested'):
            session_id = state['session_id']
            user_id = state['user_id']
            timestamp = state['timestamp']

            memory.save_session(
                session_id=session_id,
                user_id=user_id,
                query=state['query'],
                answer=state['final_answer'],
                quality_score=state.get('quality_score', 0.0),
                timestamp=timestamp,
                documents=state.get('documents', [])
            )
            logger.info(f"Session {session_id} saved to memory for user {user_id}")
        return state

    def interrupt_check(state: ResearchState) -> ResearchState:
        '''Check for interrupt and add message if needed.'''
        if state.get('interrupt_requested') and not state.get('error'):
            return {**state, 'error': 'Execution interrupted by user'}
        return state

    # Graph creation
    graph = StateGraph(ResearchState)

    # Add nodes
    graph.add_node('memory_check', memory_check_node)
    graph.add_node('supervisor', supervisor.run)
    graph.add_node('researcher', researcher.run)
    graph.add_node('analyst', analyst.run)
    graph.add_node('critic', critic.run)
    graph.add_node('validator', validator.run)
    graph.add_node('writer', writer.run)
    graph.add_node('save_memory', save_to_memory)
    graph.add_node('interrupt_check', interrupt_check)

    # Set entry point
    graph.set_entry_point('memory_check')

    # Routing from memory check
    def route_from_memory(state: ResearchState) -> str:
        if state.get('interrupt_requested'):
            return 'interrupt_check'
        if state.get('final_answer'):
            return 'save_memory'
        return 'supervisor'

    graph.add_conditional_edges(
        'memory_check',
        route_from_memory,
        {'supervisor': 'supervisor', 'save_memory': 'save_memory', 'interrupt_check': 'interrupt_check'}
    )

    # ━━━ Edges ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Researcher always reports to Validator for auditing
    graph.add_edge('researcher', 'validator')
    
    # Validator reports to supervisor for next decision
    graph.add_edge('validator', 'supervisor')

    # Analyst output goes to critic for quality check
    graph.add_edge('analyst', 'critic')

    # Writer output goes to save and end
    graph.add_edge('writer', 'save_memory')
    graph.add_edge('save_memory', END)
    graph.add_edge('interrupt_check', END)

    # ━━━ Conditional routing from supervisor ━━━━━━━━━━━━━━━━━━━━━━━━━
    graph.add_conditional_edges(
        'supervisor',
        route_from_supervisor,
        {
            'researcher': 'researcher',
            'analyst': 'analyst',
            'writer': 'writer',
            'interrupt': 'interrupt_check',
            'end': END
        }
    )

    # ━━━ Conditional routing from critic ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Critic can now route to: researcher (gaps), analyst (reanalysis), or writer (ready)
    graph.add_conditional_edges(
        'critic',
        route_from_critic,
        {
            'researcher': 'researcher',
            'analyst': 'analyst',
            'writer': 'writer',
            'interrupt': 'interrupt_check'
        }
    )

    return graph.compile()


def route_from_supervisor(state: ResearchState) -> str:
    '''Route from supervisor with interrupt check and iteration limits.'''
    # Check for interrupt
    if state.get('interrupt_requested'):
        logger.warning("Interrupt requested — stopping research")
        return 'interrupt'

    # Check iteration limit (raised to 5 for deeper research)
    cap = state.get('max_iterations', 5)
    cap = max(1, min(5, int(cap)))  # Allow up to 5 iterations
    iteration = state.get('iteration', 0)

    if iteration >= cap:
        # At limit: force to writer (or analyst if no analysis yet)
        if not state.get('analysis'):
            logger.info(f"Max iterations ({cap}) reached with no analysis — forcing analyst")
            return 'analyst'
        logger.info(f"Max iterations ({cap}) reached — forcing writer")
        return 'writer'

    next_agent = str(state.get('_next', 'researcher')).strip().lower()

    # Validate the route
    allowed = frozenset({'researcher', 'analyst', 'writer', 'end'})
    if next_agent not in allowed:
        next_agent = 'researcher'

    # Safety: don't skip directly to writer without any analysis
    if next_agent == 'writer' and not state.get('analysis'):
        logger.info("Auto-correcting: cannot write without analysis — routing to analyst")
        next_agent = 'analyst'

    # Safety: don't go to analyst without search results
    if next_agent == 'analyst' and not state.get('search_results'):
        logger.info("Auto-correcting: cannot analyze without data — routing to researcher")
        next_agent = 'researcher'

    logger.debug(f"Supervisor routing to {next_agent} (iteration {iteration}/{cap})")
    return next_agent


def route_from_critic(state: ResearchState) -> str:
    '''Route from critic: can send back to researcher (gaps), analyst (reanalysis), or writer (ready).'''
    # Check for interrupt
    if state.get('interrupt_requested'):
        logger.warning("Interrupt requested — proceeding to writer")
        return 'interrupt'

    score = state.get('quality_score', 0.0)
    iteration = state.get('iteration', 0)
    recommendation = state.get('_critic_recommendation', 'ready_to_write')
    research_gaps = state.get('research_gaps', [])

    # Hard limit: after 5 iterations, force to writer regardless
    if iteration >= 5:
        logger.warning(f"Max iterations reached (score: {score:.2f}) — forcing writer")
        return 'writer'

    # Quality is good — proceed to writer
    if score >= 0.75:
        logger.info(f"Quality threshold met (score: {score:.2f}) — proceeding to writer")
        return 'writer'

    # Quality is low but critic says "needs more research" and identified gaps
    if recommendation == 'needs_more_research' and research_gaps and iteration < 4:
        logger.info(f"Critic recommends more research (score: {score:.2f}), gaps: {research_gaps[:2]} — routing to researcher")
        return 'researcher'

    # Quality is low but no specific gaps — re-analyze with critique feedback
    if recommendation == 'needs_reanalysis' and iteration < 4:
        logger.info(f"Critic recommends reanalysis (score: {score:.2f}) — routing to analyst")
        return 'analyst'

    # Default: proceed to writer
    logger.info(f"Proceeding to writer (score: {score:.2f}, iteration: {iteration})")
    return 'writer'