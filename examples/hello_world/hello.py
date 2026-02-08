#!/usr/bin/env python3
"""Simple hello world skill for testing."""

import argparse


def main():
    parser = argparse.ArgumentParser(description="A friendly greeting skill")
    parser.add_argument(
        "--name",
        type=str,
        default="World",
        help="Name to greet",
    )
    parser.add_argument(
        "--enthusiasm",
        type=int,
        default=1,
        help="Number of exclamation marks (1-5)",
    )

    args = parser.parse_args()

    exclaim = "!" * min(max(args.enthusiasm, 1), 5)
    print(f"Hello, {args.name}{exclaim}")


if __name__ == "__main__":
    main()
