import streamlit as st
import re
import json
import requests
import yfinance as yf
from exa_py import Exa
import anthropic
from datetime import datetime, timedelta

# Page config
st.set_page_config(
    page_title="Stock Analysis Assistant",
    page_icon="📈",
    layout="wide",
)

# Initialize session state for conversation
if 'conversation' not in st.session_state:
    st.session_state.conversation = []
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Title and description
st.title("Stock Analysis Assistant")
st.markdown("Get investment analysis using AI and real-time data.")

# Sidebar for API keys
with st.sidebar:
    st.header("API Configuration")
    anthropic_key = st.text_input("Anthropic API Key", type="password")
    perplexity_key = st.text_input("Perplexity API Key", type="password")
    exa_key = st.text_input("Exa API Key", type="password")

# Tool definitions
tools = [
    {
        "name": "yahoo_finance",
        "description": (
            "Fetches stock data from Yahoo Finance. "
            "Provides pricing, volume, and market trends."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "perplexity_news",
        "description": (
            "Fetches recent news and reports using Perplexity API. "
            "Retrieves latest headlines and summaries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol (e.g., TSLA)."
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "exa_search",
        "description": (
            "Searches for financial news using Exa AI Search API. "
            "Fetches comprehensive results within date range."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol (e.g., TSLA)."
                },
                "start_date": {
                    "type": "string",
                    "description": "Start date in ISO format"
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in ISO format"
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return",
                    "default": 5
                }
            },
            "required": ["ticker", "start_date", "end_date"]
        }
    },
    {
        "name": "calculator",
        "description": (
            "Performs basic arithmetic operations. "
            "Use for numerical calculations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate"
                }
            },
            "required": ["expression"]
        }
    }
]


def fetch_yahoo_finance(ticker):
    """Fetches last week's market data for a given ticker using yfinance."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="7d")
        if hist.empty:
            msg = f"Yahoo Finance: No data for {ticker} in last week."
            return msg
        data = hist.to_string()
        return (f"Yahoo Finance: Last week's data for {ticker}:"
                f"\n{data}")
    except Exception as e:
        return f"Error fetching Yahoo Finance data: {e}"


def fetch_perplexity_news(ticker, api_key):
    """Calls Perplexity API to fetch recent news headlines."""
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Be precise and concise."},
            {"role": "user",
             "content": f"Provide latest headlines for {ticker}."}
        ],
        "max_tokens": 500,
        "temperature": 0.2,
        "top_p": 0.9,
        "top_k": 0,
        "stream": False,
        "presence_penalty": 0,
        "frequency_penalty": 1,
        "search_recency_filter": "week"
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            msg = data.get("choices", [{}])[0]
            content = msg.get("message", {}).get("content", "")
            return f"Perplexity News: {content}"
        else:
            return f"Perplexity API error: {response.text}"
    except Exception as e:
        return f"Exception in Perplexity API call: {e}"


def fetch_exa_search(ticker, start_date, end_date, api_key, num_results=5):
    """Uses the Exa AI Search API to retrieve financial news and reports."""
    try:
        exa = Exa(api_key=api_key)
        query = f"financial news on {ticker}"
        result = exa.search_and_contents(
            query, text=True, num_results=num_results,
            start_published_date=start_date,
            end_published_date=end_date,
            include_text=[ticker]
        )
        results = result.results
        if results:
            headlines = []
            for res in results:
                title = getattr(res, "title", None)
                if not title:
                    title = getattr(res, "url", "No title")
                headlines.append(title)
            results = ", ".join(headlines)
            return f"Exa Search: {len(headlines)} results: {results}"
        else:
            return f"Exa Search: No results for {ticker} in given period."
    except Exception as e:
        return f"Error fetching Exa Search results: {e}"


def calculate(expression):
    """Evaluates a sanitized arithmetic expression."""
    expression = re.sub(r'[^0-9+-*/().]', '', expression)
    try:
        result = eval(expression)
        return str(result)
    except (SyntaxError, ZeroDivisionError, NameError,
            TypeError, OverflowError):
        return "Error: Invalid expression"


def process_tool_call(tool_name, tool_input, api_keys):
    """Process tool calls and return results."""
    if tool_name == "yahoo_finance":
        return fetch_yahoo_finance(tool_input["ticker"])
    elif tool_name == "perplexity_news":
        ticker = tool_input["ticker"]
        api_key = api_keys["perplexity"]
        return fetch_perplexity_news(ticker, api_key)
    elif tool_name == "exa_search":
        ticker = tool_input["ticker"]
        start_date = tool_input["start_date"]
        end_date = tool_input["end_date"]
        num_results = tool_input.get("num_results", 5)
        api_key = api_keys["exa"]
        return fetch_exa_search(
            ticker, start_date, end_date, api_key, num_results
        )
    elif tool_name == "calculator":
        return calculate(tool_input["expression"])
    else:
        return f"Error: Unknown tool {tool_name}"


# Main input form
with st.form("stock_analysis_form"):
    ticker = st.text_input("Enter stock ticker").strip().upper()
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start date",
            value=datetime.now() - timedelta(days=30)
        )
    with col2:
        end_date = st.date_input(
            "End date",
            value=datetime.now()
        )
    submit_button = st.form_submit_button("Analyze")

# Process form submission
if submit_button:
    if not (anthropic_key and perplexity_key and exa_key):
        st.error("Please provide all required API keys in the sidebar.")
    elif not ticker:
        st.error("Please enter a stock ticker.")
    else:
        api_keys = {
            "anthropic": anthropic_key,
            "perplexity": perplexity_key,
            "exa": exa_key
        }
        client = anthropic.Anthropic(api_key=anthropic_key)
        system_prompt = (
            "You are an investment assistant. Your task is to analyze and "
            "assess the given stock. Use these tools:\n\n"
            "1. yahoo_finance: Get stock data (price, volume)\n"
            "2. perplexity_news: Fetch news headlines\n"
            "3. exa_search: Search for financial news within date range\n"
            "4. calculator: Perform arithmetic calculations\n\n"
            "Use tools when needed and add results to your recommendation. "
            "When done, provide your final verdict."
        )
        user_prompt = (
            f"Analyze investment potential for {ticker}. "
            "Review market data and news. "
            "Use APIs to gather info. "
            "Use search and calculator for analysis. "
            "Run calculator twice."
        )
        # Initialize conversation if empty
        if not st.session_state.conversation:
            st.session_state.conversation = [
                {"role": "user", "content": user_prompt}
            ]

        # Create a placeholder for the analysis
        analysis_placeholder = st.empty()

        with st.expander("Analysis Progress", expanded=True):
            while True:
                response = client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=4096, system=system_prompt,
                    tools=tools, messages=st.session_state.conversation
                )
                st.session_state.conversation.append(
                    {"role": "assistant", "content": response.content}
                )
                tool_called = False
                for block in response.content:
                    if block.type == "tool_use":
                        tool_called = True
                        tool_name = block.name
                        tool_input = block.input

                        # Show progress
                        st.info(f"Using {tool_name}: {json.dumps(tool_input)}")

                        result = process_tool_call(
                            tool_name, tool_input, api_keys
                        )
                        st.success(f"Result: {result}")

                        msg = {
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result
                            }]
                        }
                        st.session_state.conversation.append(msg)
                        break
                if not tool_called:
                    final_answer = "".join(
                        block.text for block in response.content
                        if block.type == "text")
                    analysis_placeholder.markdown(
                        f"### Investment Analysis\n{final_answer}")
                    break
        st.session_state.conversation = []
