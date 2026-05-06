from langgraph.graph import StateGraph, END
from graph.state import ResearchState
from agents.supervisor import SupervisorAgent
from agents.researcher import ResearchAgent
from agents.analyst import AnalystAgent
from agents.critic import CriticAgent
from agents.writer import WriterAgent
from memory.session_memory import SessionMemory
import logging

logger = logging.getLogger(__name__)

def build_research_graph():
    '''Build and return the compiled LangGraph research agent with interrupt support.'''

    # Agent instantiation
    supervisor = SupervisorAgent()
    researcher = ResearchAgent()
    analyst = AnalystAgent()
    critic = CriticAgent()
    writer = WriterAgent()
    memory = SessionMemory()

    def memory_check_node(state: ResearchState) -> ResearchState:
        '''Short-circuit the graph if a cached answer exists.'''
        if state.get('interrupt_requested'):
            return {**state, 'final_answer': '[Interrupted by user]', 'error': 'User interrupted execution'}

        cached = memory.is_cache_hit(state['query'])
        if cached:
            logger.info(f"Cache hit for query: {state['query'][:50]}...")
            return {**state, 'final_answer': cached}
        return state

    def save_to_memory(state: ResearchState) -> ResearchState:
        '''Persist the final answer after the Writer completes.'''
        if state.get('final_answer') and not state.get('interrupt_requested'):
            memory.save_session(
                query=state['query'],
                answer=state['final_answer'],
                quality_score=state.get('quality_score', 0.0),
                documents=state.get('documents', [])
            )
            logger.info("Session saved to memory")
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

    # Fixed edges
    graph.add_edge('researcher', 'supervisor')
    graph.add_edge('analyst', 'critic')
    graph.add_edge('writer', 'save_memory')
    graph.add_edge('save_memory', END)
    graph.add_edge('interrupt_check', END)

    # Conditional routing from supervisor
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

    # Conditional routing from critic
    graph.add_conditional_edges(
        'critic',
        route_from_critic,
        {
            'analyst': 'analyst',
            'writer': 'writer',
            'interrupt': 'interrupt_check'
        }
    )

    return graph.compile()


def _normalize_supervisor_route(raw: object) -> str:
    """Map model output to a valid conditional edge branch name."""
    nxt = str(raw or 'researcher').strip().lower()
    allowed = frozenset({'researcher', 'analyst', 'writer', 'end'})
    if nxt in allowed:
        return nxt
    if nxt == 'critic':
        return 'analyst'
    return 'researcher'


def route_from_supervisor(state: ResearchState) -> str:
    '''Route from supervisor with interrupt check and iteration limits.'''
    # Check for interrupt
    if state.get('interrupt_requested'):
        logger.warning("Interrupt requested - stopping research")
        return 'interrupt'

    # Check iteration limit
    cap = state.get('max_iterations', 5)
    cap = max(1, min(3, int(cap)))  # Hard cap at 3 iterations max
    iteration = state.get('iteration', 0)

    if iteration >= cap:
        logger.info(f"Max iterations ({cap}) reached - proceeding to writer")
        return 'writer'

    next_agent = _normalize_supervisor_route(state.get('_next'))

    # Enforce routing logic: if we have search results but no analysis, must go to analyst
    has_search = bool(state.get('search_results'))
    has_analysis = bool(state.get('analysis'))

    if has_search and not has_analysis and next_agent != 'analyst':
        logger.info("Auto-correcting route: have search results but no analysis - routing to analyst")
        next_agent = 'analyst'

    logger.debug(f"Supervisor routing to {next_agent} (iteration {iteration + 1}/{cap})")
    return next_agent


def route_from_critic(state: ResearchState) -> str:
    '''Route from critic with quality assessment and interrupt check.'''
    # Check for interrupt
    if state.get('interrupt_requested'):
        logger.warning("Interrupt requested - proceeding to writer")
        return 'interrupt'

    score = state.get('quality_score', 0.0)
    iteration = state.get('iteration', 0)

    # Decide if quality is acceptable or if we've exceeded iteration limit
    if score >= 0.75:
        logger.info(f"Quality threshold met (score: {score:.2f}) - proceeding to writer")
        return 'writer'

    if iteration >= 3:
        logger.warning(f"Max critic iterations reached (score: {score:.2f}) - forcing writer")
        return 'writer'

    logger.info(f"Quality score {score:.2f} below threshold - looping back to analyst")
    return 'analyst'