## Notes

- Creates a separate worker thread which handles all things pyserial
- Use threading events to signal a write action from the user_interface, i.e. main thread.
- How to push data back, from a large read, to the primary? Create a separate class with inherent locking?
