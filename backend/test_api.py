"""
API Testing Script
Test all endpoints of the People Counting API
"""

import requests
import json
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()

BASE_URL = "http://localhost:8000"


def print_section(title):
    """Print section header"""
    console.rule(f"[bold blue]{title}[/bold blue]")
    print()


def test_endpoint(method, endpoint, data=None, params=None):
    """Test an endpoint and display results"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, params=params)
        elif method == "POST":
            response = requests.post(url, json=data)
        elif method == "PUT":
            response = requests.put(url, json=data)
        elif method == "DELETE":
            response = requests.delete(url)
        
        console.print(f"[cyan]{method}[/cyan] {endpoint}")
        console.print(f"Status: [green]{response.status_code}[/green]")
        
        if response.status_code == 200 or response.status_code == 201:
            result = response.json()
            console.print(f"Response: {json.dumps(result, indent=2, default=str)[:500]}...")
            return True, result
        else:
            console.print(f"[red]Error: {response.text}[/red]")
            return False, None
            
    except Exception as e:
        console.print(f"[red]Exception: {e}[/red]")
        return False, None
    finally:
        print()


def main():
    """Main testing function"""
    console.print("[bold green]🧪 API Testing Script[/bold green]")
    console.print(f"Testing API at: {BASE_URL}")
    print()
    
    # Test 1: Health Check
    print_section("1. Health & Info Endpoints")
    test_endpoint("GET", "/health")
    test_endpoint("GET", "/")
    test_endpoint("GET", "/api/info")
    
    # Test 2: Statistics Endpoints
    print_section("2. Statistics Endpoints")
    
    # Live stats
    test_endpoint("GET", "/api/stats/live")
    
    # Historical stats
    test_endpoint("GET", "/api/stats/", params={
        "hours": 24,
        "include_hourly": True
    })
    
    # Detections
    success, detections = test_endpoint("GET", "/api/stats/detections", params={
        "limit": 10
    })
    
    if success and detections:
        console.print(f"[green]Found {len(detections)} detections[/green]")
    
    # Events
    success, events = test_endpoint("GET", "/api/stats/events", params={
        "limit": 10,
        "event_type": "entry"
    })
    
    if success and events:
        console.print(f"[green]Found {len(events)} events[/green]")
    
    # Forecast
    test_endpoint("POST", "/api/stats/forecast", data={
        "area_name": "high_risk_area_1",
        "periods": 24
    })
    
    # Test 3: Configuration Endpoints
    print_section("3. Configuration Endpoints")
    
    # Get all areas
    success, areas = test_endpoint("GET", "/api/config/areas")
    
    if success and areas:
        console.print(f"[green]Found {len(areas)} areas[/green]")
    
    # Get specific area
    test_endpoint("GET", "/api/config/area/high_risk_area_1")
    
    # Create test area
    test_area_name = "test_area_" + datetime.now().strftime("%Y%m%d%H%M%S")
    
    success, created = test_endpoint("POST", "/api/config/area", data={
        "area_name": test_area_name,
        "coordinates": [[100, 100], [400, 100], [400, 400], [100, 400]],
        "description": "Test area created by test script"
    })
    
    if success:
        console.print(f"[green]✓ Created test area: {test_area_name}[/green]")
        
        # Update test area
        test_endpoint("PUT", f"/api/config/area/{test_area_name}", data={
            "coordinates": [[150, 150], [450, 150], [450, 450], [150, 450]],
            "description": "Updated test area"
        })
        
        # Delete test area
        test_endpoint("DELETE", f"/api/config/area/{test_area_name}")
        console.print(f"[green]✓ Cleaned up test area[/green]")
    
    # Test 4: Summary
    print_section("4. Test Summary")
    
    # Get final stats
    success, stats = test_endpoint("GET", "/api/stats/", params={"hours": 1})
    
    if success and stats:
        summary = stats.get("summary", {})
        
        table = Table(title="Current Statistics (Last 1 Hour)")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Entry Count", str(summary.get("entry_count", 0)))
        table.add_row("Exit Count", str(summary.get("exit_count", 0)))
        table.add_row("Net Count", str(summary.get("net_count", 0)))
        table.add_row("Total Detections", str(stats.get("total_detections", 0)))
        table.add_row("Unique Tracks", str(stats.get("unique_tracks", 0)))
        
        console.print(table)
    
    print()
    console.print("[bold green]✅ Testing Complete![/bold green]")
    console.print("\n[yellow]💡 Tip:[/yellow] Visit http://localhost:8000/docs for interactive API documentation")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Testing interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")