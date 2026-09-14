import argparse


def alpha() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alpha-only")
    parser.parse_args()


def beta() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--beta-only")
    parser.parse_args()
