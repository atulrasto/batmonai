#pragma once
#include <Arduino.h>
#include <deque>
#include "config.h"

// Circular store-and-forward buffer for telemetry frames.
// Oldest frame is dropped when capacity is exceeded.
class PayloadBuffer {
public:
    void   push(const String &frame);
    void   pushFront(const String &frame);  // re-insert on failed drain
    String pop();
    bool   empty() const { return _q.empty(); }
    size_t size()  const { return _q.size(); }
private:
    std::deque<String> _q;
};
