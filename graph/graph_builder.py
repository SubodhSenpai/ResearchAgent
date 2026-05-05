from langgraph.graph import StateGraph, END
from graph.state import ResearchState
from agents.supervisor import SupervisorAgent
from agents.researcher import ResearchAgent
from agents.analyst import AnalystAgent
from agents.critic import CriticAgent
from agents.writer import WriterAgent

def build_research_graph():
    '''Build and return the compiled LangGraph research agent.'''


    #Agent intantiation
    supervisor = SupervisorAgent()
    researcher = ResearchAgent()
    analyst = AnalystAgent()
    critic = CriticAgent()
    writer = WriterAgent()

    #graph creation
    graph = StateGraph(ResearchState)

    #Add nodes
    graph.add_node('supervisor', supervisor.run)
    graph.add_node('researcher', researcher.run)
    graph.add_node('analyst', analyst.run)
    graph.add_node('critic', critic.run)
    graph.add_node('writer', writer.run)

    #set entry points
    graph.set_entry_point('supervisor')


    #fixed edges
    graph.add_edge('researcher', 'supervisor')
    graph.add_edge('analyst', 'critic')
    graph.add_edge('writer', END)

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
    graph.add_conditionaL_edges(
        'critic',
        route_from_critic,
        {
            'analyst': 'analyst',        #Loop back if quality too low
            'writer': 'writer'           # Proceed if quality ok
        }
    )

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