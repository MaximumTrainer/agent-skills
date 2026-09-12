// Tiny program used by the smoke test to prove the Go template builds,
// runs as non-root, and can find CA certificates in the final image.
package main

import (
	"crypto/x509"
	"fmt"
	"os"
)

func main() {
	pool, err := x509.SystemCertPool()
	certs := err == nil && pool != nil && !pool.Equal(x509.NewCertPool())
	fmt.Printf("hello uid=%d certs=%t\n", os.Getuid(), certs)
}
