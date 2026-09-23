# Third-party notices

## Vibe-Trading

Technical-indicator confirmation logic in `src/market_sentinel/vibe_indicators.py`
and the evidence-gated journal/walk-forward methodology in
`src/market_sentinel/learning.py` are adapted from
[HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading).

MIT License

Copyright (c) 2026 Vibe-Trading Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## @solana/web3.js 1.98.0 and qrcode-generator 1.4.4

`src/market_sentinel/static/vendor/solana-web3.iife.min.js` is the unmodified
browser build of [@solana/web3.js](https://github.com/solana-labs/solana-web3.js)
(MIT License, Copyright (c) 2023 Solana Labs, Inc.) and
`src/market_sentinel/static/vendor/qrcode-generator.js` is
[qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator)
(MIT License, Copyright (c) 2009 Kazuhiko Arase). Both are loaded only when a
user opens the VIP payment flow.
