from __future__ import annotations

import argparse
import json

from backend.app.simulation.scenario_engine import ScenarioEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate PharmaVerse AI telemetry scenarios.")
    parser.add_argument("--list", action="store_true", help="List available scenarios.")
    parser.add_argument("--scenario", choices=ScenarioEngine().list_scenarios(), help="Scenario to generate.")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of a summary.")
    args = parser.parse_args()

    if args.list:
        print("\n".join(ScenarioEngine().list_scenarios()))
        return

    scenario = ScenarioEngine().build_scenario(args.scenario)
    if args.json:
        print(json.dumps(scenario.model_dump(mode="json"), indent=2))
    else:
        print(f"Scenario: {scenario.name}")
        print(f"Description: {scenario.description}")
        print(f"Shipments: {len(scenario.shipments)}")
        print(f"Sensor readings: {len(scenario.sensor_readings)}")
        print(f"RFID events: {len(scenario.rfid_events)}")


if __name__ == "__main__":
    main()
