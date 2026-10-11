#ifndef STREAM_MIRROR_H
#define STREAM_MIRROR_H

// Rendering only: never transform note data, input mappings, or player options.
inline thread_local bool g_StreamMirrorDrawing = false;

class StreamMirrorDrawScope {
 public:
  StreamMirrorDrawScope() : previous(g_StreamMirrorDrawing) {
    g_StreamMirrorDrawing = true;
  }
  ~StreamMirrorDrawScope() { g_StreamMirrorDrawing = previous; }

 private:
  bool previous;
};

#endif
