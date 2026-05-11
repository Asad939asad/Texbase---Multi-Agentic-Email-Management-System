#!/usr/bin/python3
import os
import sys
import subprocess
from typing import Annotated, Sequence, TypedDict, Literal
from pydantic import BaseModel, Field

try:
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
    from langchain_core.tools import tool
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.message import add_messages
    from langgraph.prebuilt import ToolNode
    from langgraph.checkpoint.memory import MemorySaver
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError as e:
    print(f"Missing required library: {e}")
    sys.exit(1)

if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = "AIzaSyBNpkJkdsEHFDezctWxPKhAuFrIfFcNy1s"

PYTHON_BIN = "/Volumes/ssd2/TEXBASE/venv/bin/python3"
SRC_DIR = "/Volumes/ssd2/TEXBASE/src"

# ══════════════════════════════════════════════════════════════════════════════
#  GRAPH STATE & REAL TOOLS
# ══════════════════════════════════════════════════════════════════════════════
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next_node: str

# --- CashFlow Tool ---
class CashFlowArgs(BaseModel):
    input_type: Literal["text", "file", "email"] = Field(
        description="The format of the input. Use 'text' for plain text descriptions, 'file' for PDF/image paths, and 'email' for email text file paths."
    )
    input_value: str = Field(
        description="The actual text description, or the absolute file path."
    )

@tool(args_schema=CashFlowArgs)
def cashflow_tool(input_type: str, input_value: str) -> str:
    """Logs financial transactions using the CashFlowCareTaker agent based on text, a file, or an email."""
    cashflow_dir = os.path.join(SRC_DIR, "CashFlowCareTaker")
    script_path = os.path.join(cashflow_dir, "main.py")
    
    cmd = [PYTHON_BIN, script_path]
    if input_type == "text":
        cmd.extend(["--text", input_value])
    elif input_type == "file":
        cmd.extend(["--file", input_value])
    elif input_type == "email":
        cmd.extend(["--email", input_value])
        
    print(f"\n[Tool Execution] Running CashFlow agent with cmd: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, cwd=cashflow_dir, capture_output=True, text=True)
        return f"CashFlow Output:\n{res.stdout}\nErrors if any:\n{res.stderr}"
    except Exception as e:
        return f"Failed to execute CashFlow Agent: {e}"

# --- PO & Quotation Tools ---
class ProcessPOArgs(BaseModel):
    file_path: str = Field(description="Absolute path to the PO file (PDF or image) to process/extract data from. Use this if the user wants to 'enter', 'read', or process a new document so it goes into the database.")

@tool(args_schema=ProcessPOArgs)
def process_po_tool(file_path: str) -> str:
    """Processes a Purchase Order file using the PO pipeline (extracts to database). If the user asks to get quotations for a raw file/image, YOU MUST RUN THIS TOOL FIRST to extract its data before predicting quotations!"""
    po_dir = os.path.join(SRC_DIR, "PO:Quotation")
    script_path = os.path.join(po_dir, "po_processor.py")
    
    cmd = [PYTHON_BIN, script_path, "--file", file_path]
    print(f"\n[Tool Execution] Running PO_Manager (Processor) on {file_path}...")
    try:
        res = subprocess.run(cmd, cwd=po_dir, capture_output=True, text=True)
        return f"PO Processing Output:\n{res.stdout}\nErrors if any:\n{res.stderr}"
    except Exception as e:
        return f"Failed to execute PO Processor: {e}"


class PredictQuotationArgs(BaseModel):
    source_file: str = Field(default="", description="The exact filename (e.g. 'my_po.pdf' or 'image.png') ALREADY present in the PO database. If the file was never processed, run process_po_tool first!")
    table_name: str = Field(default="", description="Optional: specific table name to query. If source_file is omitted, you MUST provide this.")

@tool(args_schema=PredictQuotationArgs)
def predict_quotation_tool(source_file: str = "", table_name: str = "") -> str:
    """Predicts pricing for PO line items using the Quotation Predictor tool and Google Search. Document must already be in the PO database."""
    po_dir = os.path.join(SRC_DIR, "PO:Quotation")
    script_path = os.path.join(po_dir, "quotation_predictor.py")
    
    cmd = [PYTHON_BIN, script_path]
    if source_file:
        cmd.extend(["--source", source_file])
    if table_name:
        cmd.extend(["--table", table_name])
        
    print(f"\n[Tool Execution] Running PO_Manager (Predictor) for source_file='{source_file}' table='{table_name}'...")
    try:
        res = subprocess.run(cmd, cwd=po_dir, capture_output=True, text=True)
        return f"Quotation Prediction Output:\n{res.stdout}\nErrors if any:\n{res.stderr}"
    except Exception as e:
        return f"Failed to execute Quotation Predictor: {e}"


# --- Research Tools ---
class RunDeepResearchArgs(BaseModel):
    query: str = Field(default="", description="Optional: specific research prompt to investigate. Leaves default if blank.")
    topic: str = Field(default="Deep_Research_Textile_Report", description="Optional: Short topic name for file and table generation.")

@tool(args_schema=RunDeepResearchArgs)
def run_deep_research_tool(query: str = "", topic: str = "Deep_Research_Textile_Report") -> str:
    """Runs the Deep Research Agent to generate a PDF report. If a query is provided, it researches that specific query and saves it under the topic name. If not, it runs the default global textile prompts. Very slow, takes several minutes."""
    research_dir = os.path.join(SRC_DIR, "ResearchAgent")
    brain_script = os.path.join(research_dir, "researchBrain.py")
    parser_script = os.path.join(research_dir, "Information_parser.py")
    
    # 1. Generate the PDF Report
    cmd_brain = [PYTHON_BIN, brain_script]
    if query:
        cmd_brain.extend(["--query", query, "--topic", topic])
    
    print(f"\n[Tool Execution] Running Research_Manager (Deep Research PDF generation)...")
    try:
        res_brain = subprocess.run(cmd_brain, cwd=research_dir, capture_output=True, text=True)
        if res_brain.returncode != 0:
             return f"Failed during Deep Research Phase:\n{res_brain.stderr}"
    except Exception as e:
        return f"Failed to execute Deep Research: {e}"

    # 2. Extract Data into Database
    safe_topic = re.sub(r'[^A-Za-z0-9_\-]', '_', topic)
    pdf_filename = f"{safe_topic}.pdf"
    
    # Generate daily table name (e.g. 2026_03_10_Topic)
    date_str = datetime.datetime.now().strftime("%Y_%m_%d")
    table_name = f"{date_str}_{safe_topic}"

    cmd_parser = [PYTHON_BIN, parser_script, "--target", pdf_filename, "--table", table_name]
    print(f"\n[Tool Execution] Running Research_Manager (Information Parsing into {table_name})...")
    try:
        res_parser = subprocess.run(cmd_parser, cwd=research_dir, capture_output=True, text=True)
        if res_parser.returncode != 0:
             return f"Failed during Information Parsing Phase:\n{res_parser.stderr}"
    except Exception as e:
        return f"Failed to execute Information Parser: {e}"
        
    return f"Research Complete! Database updated and you can view research on the trends page. Table created: {table_name}"


class ParseResearchInfoArgs(BaseModel):
    pass

@tool(args_schema=ParseResearchInfoArgs)
def parse_research_information_tool() -> str:
    """Parses all PDFs in the research_pdf folder to extract self-contained news snippets into the default news_items table."""
    research_dir = os.path.join(SRC_DIR, "ResearchAgent")
    script_path = os.path.join(research_dir, "Information_parser.py")
    
    cmd = [PYTHON_BIN, script_path]
    print(f"\n[Tool Execution] Running Research_Manager (Information Parser Bulk)...")
    try:
        res = subprocess.run(cmd, cwd=research_dir, capture_output=True, text=True)
        return f"Information Parser Output:\n{res.stdout}\nErrors if any:\n{res.stderr}"
    except Exception as e:
        return f"Failed to execute Information Parser: {e}"


class GenerateColdEmailArgs(BaseModel):
    # No arguments needed, it draws from the importyeti database queue
    pass

@tool(args_schema=GenerateColdEmailArgs)
def generate_cold_email_tool() -> str:
    """Generates a cold email outreach draft for the next queued company by executing a LangGraph pipeline that verifies emails with Hunter and enriches with Deep Research."""
    email_dir = os.path.join(SRC_DIR, "ColdEmail")
    script_path = os.path.join(email_dir, "email_specific.py")
    
    cmd = [PYTHON_BIN, script_path]
    print(f"\n[Tool Execution] Running Email_Manager (Cold Email Generation)...")
    try:
        res = subprocess.run(cmd, cwd=email_dir, capture_output=True, text=True)
        return f"Cold Email Output:\n{res.stdout}\nErrors if any:\n{res.stderr}"
    except Exception as e:
        return f"Failed to execute Cold Email Generator: {e}"


class ProcessNextFollowUpArgs(BaseModel):
    pass

@tool(args_schema=ProcessNextFollowUpArgs)
def process_next_followup_email_tool() -> str:
    """Processes the next NEW (unprocessed) email in the central FollowUp inbox, routing it and generating a draft reply."""
    followup_dir = os.path.join(SRC_DIR, "FollowUp")
    cmd = [PYTHON_BIN, os.path.join(followup_dir, "main.py"), "--run"]
    print(f"\n[Tool Execution] Running FollowUp_Manager (Process Next Email)...")
    try:
        res = subprocess.run(cmd, cwd=followup_dir, capture_output=True, text=True)
        return f"FollowUp Output:\n{res.stdout}\nErrors if any:\n{res.stderr}"
    except Exception as e:
        return f"Failed to execute FollowUp Agent: {e}"


class SimulateFollowUpArgs(BaseModel):
    email_text: str = Field(description="The body text of the email")
    sender: str = Field(default="unknown@email.com", description="The sender's email address")
    subject: str = Field(default="No Subject", description="The subject line of the email")

@tool(args_schema=SimulateFollowUpArgs)
def simulate_followup_email_tool(email_text: str, sender: str = "unknown@email.com", subject: str = "No Subject") -> str:
    """Simulates receiving an incoming email without checking the real inbox, runs the routing, and outputs the draft."""
    followup_dir = os.path.join(SRC_DIR, "FollowUp")
    cmd = [PYTHON_BIN, os.path.join(followup_dir, "main.py"), "--simulate", email_text, "--from", sender, "--subject", subject]
    print(f"\n[Tool Execution] Running FollowUp_Manager (Simulate Email)...")
    try:
        res = subprocess.run(cmd, cwd=followup_dir, capture_output=True, text=True)
        return f"FollowUp Output:\n{res.stdout}\nErrors if any:\n{res.stderr}"
    except Exception as e:
        return f"Failed to execute FollowUp Agent: {e}"


class ListInboxArgs(BaseModel):
    pass

@tool(args_schema=ListInboxArgs)
def list_inbox_emails_tool() -> str:
    """Lists all emails currently in the central FollowUp inbox, highlighting which ones are [NEW] vs [UNDER REVIEW]."""
    followup_dir = os.path.join(SRC_DIR, "FollowUp")
    cmd = [PYTHON_BIN, os.path.join(followup_dir, "main.py"), "--list"]
    print(f"\n[Tool Execution] Running FollowUp_Manager (List Inbox)...")
    try:
        res = subprocess.run(cmd, cwd=followup_dir, capture_output=True, text=True)
        return f"FollowUp Output:\n{res.stdout}\nErrors if any:\n{res.stderr}"
    except Exception as e:
        return f"Failed to execute FollowUp Agent: {e}"


class ShowDraftArgs(BaseModel):
    inbox_id: int = Field(description="The integer inbox ID to view the drafted reply for.")

@tool(args_schema=ShowDraftArgs)
def show_draft_reply_tool(inbox_id: int) -> str:
    """Shows the original email and the drafted reply for a specific inbox ID."""
    followup_dir = os.path.join(SRC_DIR, "FollowUp")
    cmd = [PYTHON_BIN, os.path.join(followup_dir, "main.py"), "--draft", str(inbox_id)]
    print(f"\n[Tool Execution] Running FollowUp_Manager (Show Draft #{inbox_id})...")
    try:
        res = subprocess.run(cmd, cwd=followup_dir, capture_output=True, text=True)
        return f"FollowUp Output:\n{res.stdout}\nErrors if any:\n{res.stderr}"
    except Exception as e:
        return f"Failed to execute FollowUp Agent: {e}"


class IngestEmailFileArgs(BaseModel):
    file_path: str = Field(description="Absolute path to the email .txt file")
    sender: str = Field(default="unknown@email.com", description="The sender's email address")
    subject: str = Field(default="No Subject", description="The subject line of the email")

@tool(args_schema=IngestEmailFileArgs)
def ingest_email_file_tool(file_path: str, sender: str = "unknown@email.com", subject: str = "No Subject") -> str:
    """Ingests a text file as an email, saves it to the central inbox, and processes it."""
    followup_dir = os.path.join(SRC_DIR, "FollowUp")
    cmd = [PYTHON_BIN, os.path.join(followup_dir, "main.py"), "--email", file_path, "--from", sender, "--subject", subject]
    print(f"\n[Tool Execution] Running FollowUp_Manager (Ingest Email File)...")
    try:
        res = subprocess.run(cmd, cwd=followup_dir, capture_output=True, text=True)
        return f"FollowUp Output:\n{res.stdout}\nErrors if any:\n{res.stderr}"
    except Exception as e:
        return f"Failed to execute FollowUp Agent: {e}"


finance_tools = [cashflow_tool]
po_tools = [process_po_tool, predict_quotation_tool]
research_tools = [run_deep_research_tool, parse_research_information_tool]
email_tools = [generate_cold_email_tool]
followup_tools = [process_next_followup_email_tool, simulate_followup_email_tool, list_inbox_emails_tool, show_draft_reply_tool, ingest_email_file_tool]

# ══════════════════════════════════════════════════════════════════════════════
#  MULTI-AGENT PERSONAS & ROUTING 
# ══════════════════════════════════════════════════════════════════════════════
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
finance_agent_llm = llm.bind_tools(finance_tools)
po_agent_llm = llm.bind_tools(po_tools)
research_agent_llm = llm.bind_tools(research_tools)
email_agent_llm = llm.bind_tools(email_tools)
followup_agent_llm = llm.bind_tools(followup_tools)

class RouteDecision(BaseModel):
    next_node: Literal["Finance_Manager", "PO_Manager", "Research_Manager", "Email_Manager", "FollowUp_Manager", "FINISH"] = Field(
        description="Select the specialized agent or FINISH"
    )

supervisor_router = llm.with_structured_output(RouteDecision)

def supervisor_node(state: AgentState):
    sys_prompt = (
        "You are the Head Superagent orchestrator overseeing the AI system.\n"
        " - Finance_Manager: For parsing and recording cash flow, income, expense, or financial transactions from text, files, or emails.\n"
        " - PO_Manager: For handling processing of Purchase Orders (PO) or making quotation pricing predictions on PO line items.\n"
        " - Research_Manager: For conducting deep textile market research to generate PDF reports, or parsing those PDFs into a database of news snippets.\n"
        " - Email_Manager: For generating outreach and drafting cold emails for new prospects or companies.\n"
        " - FollowUp_Manager: For managing the central email inbox, routing incoming emails to the correct databases, evaluating threads, simulating inbound emails, and drafting replies (under review).\n"
        " - FINISH: If the user request is fully satisfied or no tools need calling.\n"
        "Analyze the user's latest request and route it. We will add more agents later."
    )
    decision = supervisor_router.invoke([("system", sys_prompt)] + state["messages"])
    return {"next_node": decision.next_node}

def finance_manager_node(state: AgentState):
    sys_prompt = "You are the Finance_Manager. You use `cashflow_tool`. Acknowledge execution results."
    res = finance_agent_llm.invoke([("system", sys_prompt)] + state["messages"])
    return {"messages": [res]}

def po_manager_node(state: AgentState):
    sys_prompt = "You are the PO_Manager. You use `process_po_tool` and `predict_quotation_tool`. Acknowledge execution results."
    res = po_agent_llm.invoke([("system", sys_prompt)] + state["messages"])
    return {"messages": [res]}

def research_manager_node(state: AgentState):
    sys_prompt = "You are the Research_Manager. You use `run_deep_research_tool` and `parse_research_information_tool`. Acknowledge execution results."
    res = research_agent_llm.invoke([("system", sys_prompt)] + state["messages"])
    return {"messages": [res]}

def email_manager_node(state: AgentState):
    sys_prompt = "You are the Email_Manager. You use `generate_cold_email_tool`. Acknowledge execution results."
    res = email_agent_llm.invoke([("system", sys_prompt)] + state["messages"])
    return {"messages": [res]}

def followup_manager_node(state: AgentState):
    sys_prompt = "You are the FollowUp_Manager. You use `process_next_followup_email_tool`, `simulate_followup_email_tool`, `list_inbox_emails_tool`, `show_draft_reply_tool`, and `ingest_email_file_tool`. Acknowledge execution results."
    res = followup_agent_llm.invoke([("system", sys_prompt)] + state["messages"])
    return {"messages": [res]}

# ---- Inter-Agent Routing ----
def route_supervisor(state: AgentState):
    if state.get("next_node") == "FINISH":
        return END
    return state.get("next_node", "FINISH")

def route_finance_manager(state: AgentState):
    last_msg = state["messages"][-1]
    return "finance_tool_node" if (hasattr(last_msg, "tool_calls") and last_msg.tool_calls) else "supervisor"

def route_po_manager(state: AgentState):
    last_msg = state["messages"][-1]
    return "po_tool_node" if (hasattr(last_msg, "tool_calls") and last_msg.tool_calls) else "supervisor"

def route_research_manager(state: AgentState):
    last_msg = state["messages"][-1]
    return "research_tool_node" if (hasattr(last_msg, "tool_calls") and last_msg.tool_calls) else "supervisor"

def route_email_manager(state: AgentState):
    last_msg = state["messages"][-1]
    return "email_tool_node" if (hasattr(last_msg, "tool_calls") and last_msg.tool_calls) else "supervisor"

def route_followup_manager(state: AgentState):
    last_msg = state["messages"][-1]
    return "followup_tool_node" if (hasattr(last_msg, "tool_calls") and last_msg.tool_calls) else "supervisor"

# ══════════════════════════════════════════════════════════════════════════════
#  BUILD GRAPH
# ══════════════════════════════════════════════════════════════════════════════
builder = StateGraph(AgentState)

builder.add_node("supervisor", supervisor_node)
builder.add_node("Finance_Manager", finance_manager_node)
builder.add_node("PO_Manager", po_manager_node)
builder.add_node("Research_Manager", research_manager_node)
builder.add_node("Email_Manager", email_manager_node)
builder.add_node("FollowUp_Manager", followup_manager_node)

builder.add_node("finance_tool_node", ToolNode(finance_tools))
builder.add_node("po_tool_node", ToolNode(po_tools))
builder.add_node("research_tool_node", ToolNode(research_tools))
builder.add_node("email_tool_node", ToolNode(email_tools))
builder.add_node("followup_tool_node", ToolNode(followup_tools))

builder.add_edge(START, "supervisor")
builder.add_conditional_edges("supervisor", route_supervisor)

builder.add_conditional_edges("Finance_Manager", route_finance_manager)
builder.add_edge("finance_tool_node", "Finance_Manager")

builder.add_conditional_edges("PO_Manager", route_po_manager)
builder.add_edge("po_tool_node", "PO_Manager")

builder.add_conditional_edges("Research_Manager", route_research_manager)
builder.add_edge("research_tool_node", "Research_Manager")

builder.add_conditional_edges("Email_Manager", route_email_manager)
builder.add_edge("email_tool_node", "Email_Manager")

builder.add_conditional_edges("FollowUp_Manager", route_followup_manager)
builder.add_edge("followup_tool_node", "FollowUp_Manager")

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════
def start_cli():
    print("="*60)
    print(" 🚀 HEAD SUPERAGENT INITIALIZED (LangGraph) ")
    print("    Currently connected agents: Finance_Manager, PO_Manager, Research_Manager, Email_Manager, FollowUp_Manager")
    print("    (Room reserved for future agents...)")
    print("="*60)
    
    thread_id = input("Enter your Session Thread ID (e.g., 'session_main'): ").strip()
    if not thread_id: thread_id = "default_thread"
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"\n[System] Restoring persistent checks for thread: {thread_id}")
    
    while True:
        try:
            user_in = input("\nUser> ")
            if user_in.lower() in ["quit", "exit"]:
                print("Exiting...")
                break
                
            printed_ids = set()
            for ev in graph.stream({"messages": [HumanMessage(content=user_in)]}, config, stream_mode="values"):
                msg = ev["messages"][-1]
                if isinstance(msg, AIMessage) and msg.content and getattr(msg, 'id', None) not in printed_ids:
                    print(f"\n[Agent]: {msg.content}")
                    if hasattr(msg, 'id'): printed_ids.add(msg.id)

        except Exception as e:
            print(f"Error during runtime loop: {e}")
            import traceback; traceback.print_exc()

if __name__ == "__main__":
    start_cli()
