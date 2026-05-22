import asyncio
import uuid
import warnings
from langchain_core.messages import HumanMessage, AIMessage
from agent.mcp_bridge import fetch_mcp_tool_schemas
from agent.graph import create_agent_graph

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")

CONVERSATIONS = [
    {
        "topic": "Transformers",
        "turns": [
            "Find 3 recent papers on Transformer architectures.",
            "Analyze the citations of the first paper in the list.",
            "Save that first paper to my library."
        ]
    },
    {
        "topic": "Q-Learning",
        "turns": [
            "Search for Q-Learning in Robotics (limit to 2).",
            "Can you try to find an open access PDF for the second paper?",
            "Compare the first and second paper."
        ]
    },
    {
        "topic": "LLM Alignment",
        "turns": [
            "I want to do a literature review on Large Language Models alignment. Find some papers first.",
            "Now please build a comprehensive literature review on LLM alignment based on those."
        ]
    },
    {
        "topic": "Quantum Error Correction",
        "turns": [
            "Find papers about Quantum Error Correction codes.",
            "Analyze the citations of the most relevant one from the results."
        ]
    },
    {
        "topic": "Graph Neural Networks",
        "turns": [
            "Search for Graph Neural Networks applications in biology.",
            "Save the top 2 papers to my library.",
            "Export my library as BibTeX."
        ]
    }
]

async def run_simulation():
    print("Fetching tools from MCP server...")
    try:
        schemas = await fetch_mcp_tool_schemas()
    except Exception as e:
        print(f"Failed to connect to MCP server: {e}")
        print("Please make sure the MCP server is running on port 8000.")
        return

    agent = create_agent_graph(schemas, library_token="sleuth_token_abc123")
    
    for i, conv in enumerate(CONVERSATIONS):
        thread_id = str(uuid.uuid4())
        print(f"\n========================================================")
        print(f"Starting Conversation {i+1}/5: {conv['topic']}")
        print(f"Thread ID: {thread_id}")
        print(f"========================================================\n")
        
        for turn_num, user_msg in enumerate(conv['turns']):
            print(f"\n[Turn {turn_num+1}] User: {user_msg}")
            
            try:
                result = await agent.ainvoke(
                    {"messages": [HumanMessage(content=user_msg)]},
                    config={"configurable": {"thread_id": thread_id}}
                )
                
                # Print only the final AI response for this turn to avoid huge outputs
                final_content = ""
                for msg in result["messages"]:
                    if isinstance(msg, AIMessage) and msg.content:
                        final_content = msg.content
                
                if final_content:
                    print(f"[Agent]: {final_content[:300]}... [TRUNCATED]")
                else:
                    print("[Agent]: (No text response, only tool calls or empty)")

            except Exception as e:
                print(f"[Agent Error]: {e}")

if __name__ == "__main__":
    asyncio.run(run_simulation())
