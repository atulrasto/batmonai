#include "buffer.h"

void PayloadBuffer::push(const String &frame) {
    if (_q.size() >= BUFFER_MAX_FRAMES) {
        _q.pop_front();   // discard oldest to make room
        Serial.println("[buf] Buffer full — oldest frame dropped");
    }
    _q.push_back(frame);
}

void PayloadBuffer::pushFront(const String &frame) {
    _q.push_front(frame);
}

String PayloadBuffer::pop() {
    if (_q.empty()) return "";
    String s = _q.front();
    _q.pop_front();
    return s;
}
