"""
ScholarSleuth – Streamlit Chat Interface
Connects to the LangGraph ReAct agent backed by MCP tools.
"""
import asyncio
import uuid
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from agent.mcp_bridge import fetch_mcp_tool_schemas
from agent.graph import create_agent_graph
import aiosqlite
from mcp_server.db import DB_PATH

# ── Async Helper ────────────────────────────────────────────────────
def run_async(coro):
    """Run an async coroutine from synchronous Streamlit code."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Page Config ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="ScholarSleuth",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

:root {
    --bg-primary: #0E1117;
    --bg-secondary: #1A1D27;
    --bg-card: rgba(30, 34, 48, 0.85);
    --accent-blue: #4F8EF7;
    --accent-purple: #A855F7;
    --accent-gradient: linear-gradient(135deg, #4F8EF7, #A855F7);
    --text-primary: #E8EAED;
    --text-secondary: #9CA3AF;
    --border-subtle: rgba(79, 142, 247, 0.15);
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Header gradient bar */
.main-header {
    background: var(--accent-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.2rem;
    font-weight: 700;
    margin-bottom: 0;
    letter-spacing: -0.5px;
}

.sub-header {
    color: var(--text-secondary);
    font-size: 0.95rem;
    font-weight: 400;
    margin-top: -8px;
    margin-bottom: 1.5rem;
}

/* Sidebar styling */
section[data-testid="stSidebar"] {
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-subtle);
}

section[data-testid="stSidebar"] .stMarkdown h2 {
    background: var(--accent-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 1.3rem;
}

/* Chat message styling */
.stChatMessage {
    border-radius: 12px !important;
    border: 1px solid var(--border-subtle) !important;
    backdrop-filter: blur(10px);
}

/* Tool call expander */
.streamlit-expanderHeader {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
    font-size: 0.85rem !important;
    color: var(--accent-blue) !important;
}

/* Buttons */
.stButton > button {
    background: var(--accent-gradient) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.2rem !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(79, 142, 247, 0.35) !important;
}

/* Input fields */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
}

/* Status badge */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 500;
}
.status-connected {
    background: rgba(34, 197, 94, 0.15);
    color: #22C55E;
    border: 1px solid rgba(34, 197, 94, 0.3);
}
.status-disconnected {
    background: rgba(239, 68, 68, 0.15);
    color: #EF4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
}
</style>
""", unsafe_allow_html=True)


# ── Session State Init ──────────────────────────────────────────────
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "agent" not in st.session_state:
    st.session_state.agent = None

# ── Cached MCP Connection ───────────────────────────────────────────
@st.cache_resource(show_spinner="Connecting to MCP Server...")
def get_global_tool_schemas():
    """Fetch MCP tool schemas once globally for all users."""
    try:
        return run_async(fetch_mcp_tool_schemas())
    except Exception as e:
        st.error(f"Failed to connect to MCP server: {e}")
        return None

# Load schemas automatically
tool_schemas = get_global_tool_schemas()
mcp_connected = bool(tool_schemas)


# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔬 ScholarSleuth")
    st.caption("AI-Powered Academic Research Assistant")
    st.divider()

    # Connection status
    if mcp_connected:
        st.markdown(
            '<span class="status-badge status-connected">● Connected to MCP Server</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="status-badge status-disconnected">● Disconnected</span>',
            unsafe_allow_html=True,
        )
        st.caption("Please ensure the MCP server is running on port 8000.")

    st.divider()

    # User Login
    st.markdown("#### 👤 Account")
    username = st.text_input(
        "Username",
        value="researcher",
        help="Log in to access your personal saved library.",
    )

    # Fetch token silently
    library_token = None
    if username:
        async def fetch_token():
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT api_key FROM users WHERE username = ?", (username,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
        
        library_token = run_async(fetch_token())
        if library_token:
            st.success(f"Welcome back, {username}!")
        else:
            st.warning("User not found.")

    st.divider()

    # Session management
    st.markdown("#### 💬 Session")
    st.caption(f"Thread: `{st.session_state.thread_id[:8]}...`")
    if st.button("🔄 New Research Session", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.chat_history = []
        st.session_state.agent = None
        st.rerun()

    st.divider()

    # Available tools display
    if tool_schemas:
        st.markdown("#### 🛠️ Available Tools")
        tool_names = {
            "tool_search_papers": ("🔍", "Search Papers"),
            "tool_analyze_citations": ("📊", "Analyze Citations"),
            "tool_get_open_access_pdf": ("📄", "Find Open Access PDF"),
            "tool_save_to_library": ("💾", "Save to Library"),
            "tool_export_bibtex": ("📑", "Export BibTeX"),
            "tool_compare_papers": ("⚖️", "Compare Papers"),
            "tool_build_literature_review": ("📝", "Literature Review"),
        }
        for schema in tool_schemas:
            name = schema["function"]["name"]
            icon, label = tool_names.get(name, ("🔧", name))
            st.caption(f"{icon} {label}")


# ── Build / Rebuild Agent ───────────────────────────────────────────
def get_or_create_agent():
    """Lazily create (or rebuild) the LangGraph agent."""
    if st.session_state.agent is None and tool_schemas:
        st.session_state.agent = create_agent_graph(
            tool_schemas=tool_schemas,
            library_token=library_token,
        )
    return st.session_state.agent


# ── Main Chat Area ──────────────────────────────────────────────────
st.markdown('<p class="main-header">ScholarSleuth</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">Your AI research companion — search, analyze, and synthesize academic literature.</p>',
    unsafe_allow_html=True,
)

# Render existing chat history
for msg in st.session_state.chat_history:
    role = msg["role"]
    with st.chat_message(role, avatar="🧑‍🔬" if role == "user" else "🔬"):
        # If there are tool calls in the message, show them in an expander
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                with st.expander(f"🛠️ Called: `{tc['name']}`", expanded=False):
                    st.json(tc["args"])
        if msg.get("tool_results"):
            for tr in msg["tool_results"]:
                with st.expander(f"📋 Tool Result", expanded=False):
                    st.markdown(tr[:2000] if len(tr) > 2000 else tr)
        if msg.get("content"):
            st.markdown(msg["content"])


# ── Chat Input ──────────────────────────────────────────────────────
if prompt := st.chat_input("Ask me about any research topic..."):
    if not mcp_connected:
        st.error("⚠️ Cannot connect to the MCP Server. Is it running on port 8000?")
        st.stop()

    agent = get_or_create_agent()
    if agent is None:
        st.error("⚠️ Agent not initialized. Connect to the MCP server first.")
        st.stop()

    # Show user message
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍🔬"):
        st.markdown(prompt)

    # Invoke agent
    with st.chat_message("assistant", avatar="🔬"):
        with st.spinner("Researching..."):
            try:
                result = run_async(
                    agent.ainvoke(
                        {"messages": [HumanMessage(content=prompt)]},
                        config={"configurable": {"thread_id": st.session_state.thread_id}},
                    )
                )

                # Process all messages returned by the agent
                tool_calls_display = []
                tool_results_display = []
                final_content = ""

                for msg in result["messages"]:
                    if isinstance(msg, AIMessage):
                        if msg.tool_calls:
                            for tc in msg.tool_calls:
                                tool_calls_display.append(
                                    {"name": tc["name"], "args": tc["args"]}
                                )
                                with st.expander(
                                    f"🛠️ Called: `{tc['name']}`", expanded=False
                                ):
                                    st.json(tc["args"])
                        if msg.content:
                            final_content = msg.content
                    elif isinstance(msg, ToolMessage):
                        tool_results_display.append(msg.content)
                        with st.expander("📋 Tool Result", expanded=False):
                            display_content = (
                                msg.content[:2000]
                                if len(msg.content) > 2000
                                else msg.content
                            )
                            st.markdown(display_content)

                # Display the final response
                if final_content:
                    st.markdown(final_content)

                # Save to chat history
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": final_content,
                    "tool_calls": tool_calls_display,
                    "tool_results": tool_results_display,
                })

            except Exception as e:
                st.error(f"Agent error: {e}")
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"❌ Error: {str(e)}",
                })
