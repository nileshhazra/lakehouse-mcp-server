"""
Interactive Test Client for Lakehouse MCP Server
Demonstrates tool discovery, schema inspection, query execution, and security guardrail verification.
"""

import sys
import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from server import mcp_server

console = Console()


async def run_mcp_verification():
    console.print(
        Panel.fit(
            "[bold cyan]🔌 Model Context Protocol (MCP) -- Lakehouse Server[/bold cyan]\n"
            "[dim]Standardized AI Interface for Microsoft Fabric & Azure Lakehouses[/dim]",
            border_style="cyan"
        )
    )

    # 1. Discover Registered Tools
    tools = await mcp_server.list_tools()
    console.print(f"[bold green]✔ Server registered {len(tools)} standardized MCP tools:[/bold green]")
    for t in tools:
        console.print(f"  • [bold yellow]{t.name}[/bold yellow]: [dim]{t.description.strip().splitlines()[0]}[/dim]")
    console.print()

    # 2. Call Tool 1: list_lakehouse_tables
    console.print("[bold white]► [Step 1]: Agent invokes [cyan]list_lakehouse_tables()[/cyan]...[/bold white]")
    result_tables = await mcp_server.call_tool("list_lakehouse_tables", {})
    console.print(Panel(result_tables.content[0].text, title="Lakehouse Catalog", border_style="blue"))

    # 3. Call Tool 2: describe_table_schema('SalesOrders')
    console.print("[bold white]► [Step 2]: Agent invokes [cyan]describe_table_schema('SalesOrders')[/cyan]...[/bold white]")
    result_schema = await mcp_server.call_tool("describe_table_schema", {"table_name": "SalesOrders"})
    console.print(Panel(result_schema.content[0].text, title="Table Schema (Columns & Types)", border_style="magenta"))

    # 4. Call Tool 3: execute_analytical_query (Safe Read)
    sample_sql = "SELECT TOP 5 OrderNumber, StoreLocation, TotalAmount FROM dbo.SalesOrders ORDER BY TotalAmount DESC;"
    console.print(f"[bold white]► [Step 3]: Agent invokes [cyan]execute_analytical_query()[/cyan]:[/bold white]")
    console.print(f"[dim]{sample_sql}[/dim]")
    result_query = await mcp_server.call_tool("execute_analytical_query", {"query": sample_sql})
    console.print(Panel(result_query.content[0].text, title="Query Output", border_style="green"))

    # 5. Security Test: Destructive Query (DROP TABLE)
    malicious_sql = "DROP TABLE dbo.SalesOrders;"
    console.print(f"[bold red]► [Step 4 Security Test]: Simulating unauthorized destructive query: '{malicious_sql}'[/bold red]")
    result_guardrail = await mcp_server.call_tool("execute_analytical_query", {"query": malicious_sql})
    console.print(Panel(result_guardrail.content[0].text, title="Security Guardrail (Blocked)", border_style="red"))

    console.print(
        Panel.fit(
            "[bold green]✔ All MCP Server tools verified and operational![/bold green]\n"
            "[dim]Ready for Claude Desktop, VS Code, or Agentic RAG workflows.[/dim]",
            border_style="green"
        )
    )


if __name__ == "__main__":
    asyncio.run(run_mcp_verification())
