package main

import (
    "flag"
    "fmt"
)

func main() {
    name := flag.String("name", "world", "name to greet")
    fmt.Println("hello", *name)
}
