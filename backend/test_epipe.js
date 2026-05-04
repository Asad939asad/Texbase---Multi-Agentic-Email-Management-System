const { spawnSync } = require('child_process');
const payload = { "test": "A".repeat(50*1024*1024) }; // 50MB
const res = spawnSync('python3', ['-c', 'import sys; raw = sys.stdin.read(); sys.stdout.write("read " + str(len(raw)))'], {
  input: JSON.stringify(payload)
});
console.log(res);
