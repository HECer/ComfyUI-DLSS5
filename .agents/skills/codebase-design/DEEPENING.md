# Deepening

Classify dependencies before moving shallow behavior behind one interface.

1. **In-process:** pure computation or in-memory state. Merge and test through the new interface.
2. **Local-substitutable:** a real local stand-in exists, such as an in-memory filesystem. Test the
   module with that stand-in; the seam can remain internal.
3. **Remote but owned:** define a port at the seam. Use the production transport adapter and an
   in-memory test adapter.
4. **True external:** inject a narrow port for the third-party dependency and test with a controlled
   adapter.

Replace shallow implementation tests with tests at the deepened interface once equivalent
observable coverage exists. Avoid layering both suites indefinitely. If a test must change for an
internal refactor, it is probably reaching past the interface.
