import streamlit as st
import re
import json
import requests
import yfinance as yf
from exa_py import Exa
import anthropic
from datetime import datetime, timedelta
import os

# Page config
st.set_page_config(
    page_title="Stock Analysis Assistant",
    page_icon="📈",
    layout="wide"
)

# Initialize session state for conversation
if 'conversation' not in st.session_state:
    st.session_state.conversation = []
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Title and description
st.title("Stock Analysis Assistant")
st.markdown("Get comprehensive investment analysis using AI and real-time data.")

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
            "Fetches current stock data for a given ticker from Yahoo Finance. "
            "Provides real-time pricing, volume, and market trends. "
            "Use this tool when you need quantitative data about a stock."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "The stock ticker symbol (e.g., TSLA for Tesla, Inc.)"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "perplexity_news",
        "description": (
            "Fetches recent news and financial reports for a given stock ticker using the Perplexity API. "
            "Use this tool to retrieve the latest headlines and summaries related to the stock."
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
            "Performs a detailed search for financial news and reports on a given stock ticker using the Exa AI Search API. "
            "Use this tool when you need to fetch comprehensive search results, including reports within a specific date range."
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
                    "description": "The start date for the search in ISO format."
                },
                "end_date": {
                    "type": "string",
                    "description": "The end date for the search in ISO format."
                },
                "num_results": {
                    "type": "integer",
                    "description": "The number of search results to return.",
                    "default": 5
                }
            },
            "required": ["ticker", "start_date", "end_date"]
        }
    },
    {
        "name": "calculator",
        "description": (
            "A simple calculator that performs basic arithmetic operations. "
            "Use this tool to perform any necessary calculations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate (e.g., '2 + 3 * 4')."
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
            return f"Yahoo Finance: No market data found for {ticker} in the last week."
        return f"Yahoo Finance: Last week's market data for {ticker}:\n{hist.to_string()}"
    except Exception as e:
        return f"Error fetching Yahoo Finance data: {e}"

def fetch_perplexity_news(ticker, api_key):
    """Calls the Perplexity Chat Completions API to fetch recent news headlines for a ticker."""
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Be precise and concise."},
            {"role": "user", "content": f"Provide the latest news headlines and summaries for {ticker}."}
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
            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return f"Perplexity News: {answer}"
        else:
            return f"Error fetching Perplexity news: {response.text}"
    except Exception as e:
        return f"Exception in Perplexity API call: {e}"

def fetch_exa_search(ticker, start_date, end_date, api_key, num_results=5):
    """Uses the Exa AI Search API to retrieve financial news and reports."""
    try:
        exa = Exa(api_key=api_key)
        query = f"financial news and reports on {ticker}"
        result = exa.search_and_contents(
            query,
            text=True,
            num_results=num_results,
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
            return f"Exa Search: Found {len(headlines)} results: " + ", ".join(headlines)
        else:
            return f"Exa Search: No results found for {ticker} in the given period."
    except Exception as e:
        return f"Error fetching Exa Search results: {e}"

def calculate(expression):
    """Evaluates a sanitized arithmetic expression."""
    expression = re.sub(r'[^0-9+-*/().]', '', expression)
    try:
        result = eval(expression)
        return str(result)
    except (SyntaxError, ZeroDivisionError, NameError, TypeError, OverflowError):
        return "Error: Invalid expression"

def process_tool_call(tool_name, tool_input, api_keys):
    if tool_name == "yahoo_finance":
        return fetch_yahoo_finance(tool_input["ticker"])
    elif tool_name == "perplexity_news":
        return fetch_perplexity_news(tool_input["ticker"], api_keys["perplexity"])
    elif tool_name == "exa_search":
        ticker = tool_input["ticker"]
        start_date = tool_input["start_date"]
        end_date = tool_input["end_date"]
        num_results = tool_input.get("num_results", 5)
        return fetch_exa_search(ticker, start_date, end_date, api_keys["exa"], num_results)
    elif tool_name == "calculator":
        return calculate(tool_input["expression"])
    else:
        return f"Error: Unknown tool {tool_name}"

# Main input form
with st.form("stock_analysis_form"):
    ticker = st.text_input("Enter stock ticker (e.g., TSLA)").strip().upper()
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start date for news search",
            value=datetime.now() - timedelta(days=30)
        )
    with col2:
        end_date = st.date_input(
            "End date for news search",
            value=datetime.now()
        )
    
    submit_button = st.form_submit_button("Analyze Stock")

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
            "You are an investment analysis assistant. Your task is to provide a comprehensive "
            "investment assessment for a given stock. Use the following tools as needed:\n\n"
            "1. yahoo_finance: To get real-time stock data (price, volume, trends).\n"
            "2. perplexity_news: To fetch recent news headlines and financial reports about the stock.\n"
            "3. exa_search: To perform an in-depth search for financial news and detailed reports within a specified date range.\n"
            "4. calculator: To perform any arithmetic calculations required during your analysis.\n\n"
            "Make sure to use the tools only when needed and incorporate their results into your final investment recommendation."
            "When you are done stop using tools and just provide your final verdict!!!"
        )
        
        user_prompt = (
            f"Please provide a comprehensive investment assessment for {ticker}. "
            "Include an analysis of the current stock data, recent news, and any additional financial reports if available. "
            "Use the available tools as needed: use 'yahoo_finance' for current market data, 'perplexity_news' for recent news, "
            "'exa_search' for a detailed search over a specified date range, and 'calculator' for any necessary arithmetic. "
            "Please make sure to use the calculator at least two times to generate accurate numerical results."
        )
        
        # Initialize conversation if empty
        if not st.session_state.conversation:
            st.session_state.conversation = [{"role": "user", "content": user_prompt}]
        
        # Create a placeholder for the analysis
        analysis_placeholder = st.empty()
        
        with st.expander("Analysis Progress", expanded=True):
            while True:
                response = client.messages.create(
                    model="claude-3-sonnet-20240229",
                    system=system_prompt,
                    max_tokens=4096,
                    tools=tools,
                    messages=st.session_state.conversation
                )
                
                st.session_state.conversation.append({
                    "role": "assistant",
                    "content": response.content
                })
                
                tool_called = False
                for block in response.content:
                    if block.type == "tool_use":
                        tool_called = True
                        tool_name = block.name
                        tool_input = block.input
                        
                        # Show tool call progress
                        st.info(f"Using tool: {tool_name} with input: {json.dumps(tool_input)}")
                        
                        result = process_tool_call(tool_name, tool_input, api_keys)
                        st.success(f"Tool result: {result}")
                        
                        tool_result_message = {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": result
                                }
                            ]
                        }
                        st.session_state.conversation.append(tool_result_message)
                        break
                
                if not tool_called:
                    final_answer = ""
                    for block in response.content:
                        if block.type == "text":
                            final_answer += block.text
                    
                    # Update the analysis placeholder with the final result
                    analysis_placeholder.markdown(f"### Investment Analysis\n{final_answer}")
                    break
        
        # Clear conversation for next analysis
        st.session_state.conversation = []
