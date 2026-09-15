import argparse

database = object()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real")
    parser.parse_args()
    database.option("--fake")
