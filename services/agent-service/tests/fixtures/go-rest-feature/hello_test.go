package main

import "testing"

func TestHello(t *testing.T) {
	if got := Hello(); got != "Hello, real implementation!" {
		t.Errorf("Hello() = %v, want %v", got, "Hello, real implementation!")
	}
}
