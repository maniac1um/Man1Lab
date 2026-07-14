import logging

from application import Man1Lab


def main() -> None:
    platform = Man1Lab()
    report = platform.reproduce()
    print(f"Workflow complete. Final status: {report.final_status}")
    print(f"Report written to: {report.report_path}")


if __name__ == "__main__":
    main()
