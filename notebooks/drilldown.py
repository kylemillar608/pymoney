import marimo

__generated_with = "0.3.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return mo,


@app.cell
def _(mo):
    mo.md("# Drilldown — Ad Hoc Analysis")
    return


@app.cell
def _():
    from pymoney.db import get_connection
    conn = get_connection()
    return conn,


@app.cell
def _(mo, conn):
    # Show available tables and schema
    tables = conn.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
    """).fetchdf()

    schema_info = []
    for table in tables["table_name"].tolist():
        cols = conn.execute(f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
        """).fetchdf()
        schema_info.append(f"**{table}**: " + ", ".join(
            f"`{r['column_name']}` ({r['data_type']})" for _, r in cols.iterrows()
        ))

    mo.md("## Available Tables\n\n" + "\n\n".join(schema_info))
    return schema_info, tables


@app.cell
def _(mo):
    # SQL query cell — edit the query below
    query = mo.ui.text_area(
        value="SELECT * FROM transactions LIMIT 10",
        label="SQL Query",
        rows=6,
    )
    query
    return query,


@app.cell
def _(conn, mo, query):
    import pandas as pd

    try:
        result_df = conn.execute(query.value).df()
        mo.ui.table(result_df)
    except Exception as e:
        mo.md(f"**Error:** {e}")
    return pd, result_df


@app.cell
def _(mo):
    mo.md("## Python Analysis Cell")
    return


@app.cell
def _(conn, pd):
    # Write your analysis here — conn and pd are available
    df = conn.execute("SELECT COUNT(*) AS total FROM transactions").df()
    df
    return df,


if __name__ == "__main__":
    app.run()
