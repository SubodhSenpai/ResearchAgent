from langgraph.graph import StateGraph, END
from graph.state import ResearchState
from agents.supervisor import SupervisorAgent
from agents.researcher import ResearchAgent
from agents.analyst import AnalystAgent
from agents.critic import CriticAgent
from agents.writer import WriterAgent
from memory.session_memory import SessionMemory

def build_research_graph():
    '''Build and return the compiled LangGraph research agent.'''


    #Agent intantiation
    supervisor = SupervisorAgent()
    researcher = ResearchAgent()
    analyst = AnalystAgent()
    critic = CriticAgent()
    writer = WriterAgent()
    memory = SessionMemory()

    def memory_check_node(state: ResearchState) -> ResearchState:
        '''Short-circuit the graph if a cached answer exists.'''
        cached = memory.is_cache_hit(state['query'])
        if cached:
            return {**state, 'final_answer': cached}
        return state

    def save_to_memory(state: ResearchState) -> ResearchState:
        ''' Persist the final answer after the Writer completes.'''
        if state.get('final_answer'):
            memory.save_session(
                query=state['query'],
                answer=state['final_answer'],
                quality_score=state.get('quality_score, 0.0'),
                documents=state.get('documents', [])
            )
        return state

    #graph creation
    graph = StateGraph(ResearchState)

    #Add nodes
    graph.add_node('memory_check', memory_check_node)
    graph.add_node('supervisor', supervisor.run)
    graph.add_node('researcher', researcher.run)
    graph.add_node('analyst', analyst.run)
    graph.add_node('critic', critic.run)
    graph.add_node('writer', writer.run)
    graph.add_node('save_memory', save_to_memory)

    #set entry points
    graph.set_entry_point('memory_check')


    def route_from_memory(state: ResearchState) -> str:
        return 'end' if state.get('final_answer') else 'supervisor'
    
    graph.add_conditional_edges('memory_check', route_from_memory,
    {'supervisor': 'supervisor', 'end': END})


    #fixed edges
    graph.add_edge('researcher', 'supervisor')
    graph.add_edge('analyst', 'critic')
    # graph.add_edge('writer', END)
    graph.add_edge('writer', 'save_memory')
    graph.add_edge('save_memory', END)
    #conditional routing from memory check

    #conditional routing from supervisor
    graph.add_conditional_edges(
        'supervisor',
        route_from_supervisor,
        {
            'researcher': 'researcher',
            'analyst': 'analyst',
            'writer': 'writer',
            'end': END
        }
    )

    #conditional routing from critic
    graph.add_conditional_edges(
        'critic',
        route_from_critic,
        {
            'analyst': 'analyst',        #Loop back if quality too low
            'writer': 'writer'           # Proceed if quality ok
        }
    )

    return graph.compile()

def route_from_supervisor(state: ResearchState) -> str:
    state['iteration'] = state.get('iteration', 0) + 1
    if state.get('iteration', 0) >= 5:
        return 'writer'                  #Force exit after 5 iterations
    return state.get('_next', 'researcher')

def route_from_critic(state: ResearchState) -> str:
    score = state.get('quality_score', 0.0)
    iteration = state.get('iteration', 0)
    if score >= 0.75 or iteration >= 4:
        return 'writer'
    return 'analyst'