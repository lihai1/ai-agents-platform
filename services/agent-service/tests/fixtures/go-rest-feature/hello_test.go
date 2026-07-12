package main

import (
	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
)

var _ = Describe("Hello", func() {
	It("should return the correct greeting message", func() {
		got := Hello()
		Expect(got).To(Equal("Hello, real implementation!"))
	})
})
