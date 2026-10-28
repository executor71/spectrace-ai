// Offline maintenance using the exact Badger version in Jaeger 2.6.0.
// No application database is connected. Run only against a stopped working clone.
package main

import (
    "fmt"
    "log"
    "time"
    badger "github.com/dgraph-io/badger/v4"
)

func main() {
    start := time.Now()
    options := badger.DefaultOptions("/store/jaeger/keys").WithValueDir("/store/jaeger/values")
    db, err := badger.Open(options)
    if err != nil { log.Fatal(err) }
    fmt.Println("OPEN_OK")
    // Supported compaction: expired keys are discarded by the storage engine;
    // no explicit Delete/DropAll or custom record rewrite is performed.
    if err := db.Flatten(1); err != nil { log.Fatal(err) }
    fmt.Println("FLATTEN_OK")
    if err := db.Close(); err != nil { log.Fatal(err) }
    fmt.Printf("CLOSED elapsedMs=%d\n", time.Since(start).Milliseconds())
}
