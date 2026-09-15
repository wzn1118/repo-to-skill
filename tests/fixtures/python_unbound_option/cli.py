import argparse

database = object()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real")
    database.option("--fake")
