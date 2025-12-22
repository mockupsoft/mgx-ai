#!/usr/bin/env node
const { spawn } = require('child_process');

const args = process.argv.slice(2);
const child = spawn('mgx', args, { stdio: 'inherit', shell: true });

child.on('error', (err) => {
  if (err.code === 'ENOENT') {
    console.error('❌ Error: mgx command not found.');
    console.error('Please ensure you have installed the Python package:');
    console.error('  pip install mgx-cli');
    process.exit(1);
  } else {
    console.error(`❌ Execution error: ${err.message}`);
    process.exit(1);
  }
});

child.on('close', (code) => {
  process.exit(code);
});
