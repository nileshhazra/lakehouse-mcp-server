"""
Microsoft Lakehouse Model Context Protocol (MCP) Server
Standardized AI tool interface for querying Azure SQL / Microsoft Fabric Lakehouse endpoints.
Enforces read-only execution guardrails to protect against SQL injection and destructive DDL.
"""

import os
import re
import json
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer

load_dotenv()

# Initialize MCPServer
mcp_server = MCPServer("lakehouse-mcp-server")

# Database configuration
DB_SERVER = os.getenv("DB_SERVER", "").replace("https://", "").replace("http://", "").split(":")[0]
DB_DATABASE = os.getenv("DB_DATABASE", "sqldb-retail-source")
DB_USERNAME = os.getenv("DB_USERNAME", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_PORT = int(os.getenv("DB_PORT", "1433"))


def get_db_connection():
    """Establish connection to Azure SQL DB or Fabric SQL Analytics Endpoint."""
    if not DB_SERVER or not DB_USERNAME or not DB_PASSWORD:
        raise ValueError("Missing database credentials in .env (DB_SERVER, DB_USERNAME, DB_PASSWORD).")

    try:
        import pymssql
        return pymssql.connect(
            server=DB_SERVER,
            user=DB_USERNAME,
            password=DB_PASSWORD,
            database=DB_DATABASE,
            port=DB_PORT,
            autocommit=True
        )
    except ImportError:
        import pyodbc
        conn_str = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={DB_SERVER},{DB_PORT};"
            f"DATABASE={DB_DATABASE};"
            f"UID={DB_USERNAME};"
            f"PWD={DB_PASSWORD};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
            f"Connection Timeout=30;"
        )
        return pyodbc.connect(conn_str, autocommit=True)


# ==============================================================================
# TOOL 1: List Available Tables
# ==============================================================================
@mcp_server.tool()
def list_lakehouse_tables() -> str:
    """
    Lists all available user tables in the Lakehouse database.
    Use this tool to discover available datasets before querying.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
            SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
            ORDER BY TABLE_NAME;
        """
        cursor.execute(query)
        tables = [f"{row[0]}.{row[1]} ({row[2]})" for row in cursor.fetchall()]
        return json.dumps({"available_tables": tables}, indent=2)
    finally:
        cursor.close()
        conn.close()


# ==============================================================================
# TOOL 2: Describe Table Schema
# ==============================================================================
@mcp_server.tool()
def describe_table_schema(table_name: str) -> str:
    """
    Retrieves the column names, datatypes, and nullability for a specific table.
    Input: table_name (e.g., 'SalesOrders', 'Customers', or 'dbo.SalesOrders').
    Use this tool to inspect column definitions before writing analytical queries.
    """
    clean_table = table_name.replace("dbo.", "").replace("[", "").replace("]", "")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = """
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION;
        """
        cursor.execute(query, (clean_table,))
        columns = []
        for row in cursor.fetchall():
            type_str = f"{row[1]}({row[2]})" if row[2] else row[1]
            columns.append({
                "column_name": row[0],
                "data_type": type_str,
                "is_nullable": row[3]
            })
        if not columns:
            return json.dumps({"error": f"Table '{table_name}' not found in database."}, indent=2)
        return json.dumps({"table": clean_table, "columns": columns}, indent=2)
    finally:
        cursor.close()
        conn.close()


# ==============================================================================
# TOOL 3: Execute Safe Read-Only Query
# ==============================================================================
@mcp_server.tool()
def execute_analytical_query(query: str) -> str:
    """
    Executes a read-only analytical T-SQL query on the Lakehouse database and returns tabular results.
    SAFETY GUARDRAILS:
      - Only SELECT or WITH (CTE) queries are permitted.
      - DDL/DML statements (DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, EXEC) are strictly blocked.
      - Enforces a maximum result limit of 50 rows to prevent memory exhaustion.
    """
    clean_sql = query.strip()
    destructive_keywords = [
        r"\bDROP\b", r"\bDELETE\b", r"\bUPDATE\b", r"\bINSERT\b",
        r"\bALTER\b", r"\bTRUNCATE\b", r"\bEXEC\b"
    ]
    for kw in destructive_keywords:
        if re.search(kw, clean_sql, re.IGNORECASE):
            return json.dumps({
                "error": f"Security Guardrail Violation: Destructive query detected matching pattern {kw}. Only read-only SELECT queries are allowed."
            }, indent=2)

    if not (clean_sql.upper().startswith("SELECT") or clean_sql.upper().startswith("WITH")):
        return json.dumps({"error": "Query must begin with SELECT or WITH."}, indent=2)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(clean_sql)
        col_names = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(50)
        
        result_rows = []
        for r in rows:
            row_dict = {}
            for col_name, val in zip(col_names, r):
                row_dict[col_name] = str(val) if val is not None else None
            result_rows.append(row_dict)

        return json.dumps({
            "query_executed": clean_sql,
            "row_count": len(result_rows),
            "rows": result_rows
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Query execution failed: {str(e)}"}, indent=2)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    print("[*] Starting Lakehouse MCP Server on stdio transport...")
    mcp_server.run()
