"""
ReconDragon CLI - Reconnaissance Tool
"""

import typer
import sqlite3
import json
import os
import logging
from datetime import datetime
from typing import List
import uuid
import ipaddress
import socket

# Configuration via environment variables
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./workspaces")
DB_URL = os.getenv("DB_URL", "./recon.db")

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Typer app
app = typer.Typer()

def print_banner():
    """Print ASCII banner"""
    banner = """
    ██████╗ ███████╗ ██████╗ ██████╗ ███╗   ██╗██████╗ ██████╗  █████╗  ██████╗  ██████╗ ███╗   ██╗
    ██╔══██╗██╔════╝██╔════╝██╔═══██╗████╗  ██║██╔══██╗██╔══██╗██╔══██╗██╔════╝ ██╔══██╗████╗  ██║
    ██████╔╝█████╗  ██║     ██║   ██║██╔██╗ ██║██║  ██║██████╔╝███████║██║  ███╗██████╔╝██╔██╗ ██║
    ██╔══██╗██╔══╝  ██║     ██║   ██║██║╚██╗██║██║  ██║██╔══██╗██╔══██║██║   ██║██╔══██╗██║╚██╗██║
    ██║  ██║███████╗╚██████╗╚██████╔╝██║ ╚████║██████╔╝██║  ██║██║  ██║╚██████╔╝██║  ██║██║ ╚████║
    ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝

    ReconDragon - Reconnaissance Made Powerful
    """
    typer.echo(banner)

def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            workspace TEXT,
            target TEXT,
            modules TEXT,
            status TEXT,
            created_at TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE
        )
    ''')
    conn.commit()
    conn.close()

def validate_target(target: str) -> bool:
    """Validate target is a valid domain or IP"""
    try:
        ipaddress.ip_address(target)
        return True
    except ValueError:
        try:
            socket.gethostbyname(target)
            return True
        except socket.gaierror:
            return False

@app.command()
def scan(
    target: str = typer.Option(..., help="Target to scan (IP or domain)"),
    workspace: str = typer.Option("default", help="Workspace name"),
    modules: List[str] = typer.Option(..., help="Modules to run")
):
    """
    Start a reconnaissance scan
    """
    # Input validation
    if not validate_target(target):
        typer.echo(f"Invalid target: {target}")
        raise typer.Exit(1)

    if not modules:
        typer.echo("At least one module must be specified")
        raise typer.Exit(1)

    # Valid modules list (for future expansion)
    valid_modules = ["dns", "ports", "subdomains", "web", "services"]
    invalid_modules = [m for m in modules if m not in valid_modules]
    if invalid_modules:
        typer.echo(f"Invalid modules: {', '.join(invalid_modules)}")
        typer.echo(f"Valid modules: {', '.join(valid_modules)}")
        raise typer.Exit(1)

    # Ensure workspace exists
    conn = sqlite3.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO workspaces (id, name) VALUES (?, ?)", (uuid.uuid4().hex, workspace))
    conn.commit()

    # Create job
    job_id = uuid.uuid4().hex
    job_data = {
        "id": job_id,
        "workspace": workspace,
        "target": target,
        "modules": modules,
        "status": "queued",
        "created_at": datetime.utcnow().isoformat()
    }

    # Save to database
    cursor.execute("INSERT INTO jobs (id, workspace, target, modules, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                   (job_id, workspace, target, json.dumps(modules), "queued", job_data["created_at"]))
    conn.commit()
    conn.close()

    typer.echo(f"Job created with ID: {job_id}")
    logging.info(f"Job {job_id} queued for {target} in workspace {workspace} with modules: {', '.join(modules)}")

    # TODO: Integrate with worker queue (Redis/RQ)
    # Send job_data to Redis queue for worker processing

@app.command()
def list_workspaces():
    """
    List all workspaces
    """
    conn = sqlite3.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM workspaces")
    workspaces = cursor.fetchall()
    conn.close()

    if not workspaces:
        typer.echo("No workspaces found")
    else:
        typer.echo("Workspaces:")
        for ws in workspaces:
            typer.echo(f"  - {ws[0]}")

@app.command()
def show_job(job_id: str):
    """
    Show details of a specific job
    """
    conn = sqlite3.connect(DB_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
    job = cursor.fetchone()
    conn.close()

    if not job:
        typer.echo(f"Job {job_id} not found")
        raise typer.Exit(1)

    job_details = {
        "id": job[0],
        "workspace": job[1],
        "target": job[2],
        "modules": json.loads(job[3]),
        "status": job[4],
        "created_at": job[5]
    }

    typer.echo(json.dumps(job_details, indent=2))

@app.callback()
def main():
    """
    ReconDragon CLI - Powerful Reconnaissance Tool
    """
    print_banner()
    init_db()

if __name__ == "__main__":
    app()