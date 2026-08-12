# Table of Contents
- D:\PycharmProjects\Easycode\frontend\index.html
- D:\PycharmProjects\Easycode\frontend\jsconfig.json
- D:\PycharmProjects\Easycode\frontend\package-lock.json
- D:\PycharmProjects\Easycode\frontend\package.json
- D:\PycharmProjects\Easycode\frontend\README.md
- D:\PycharmProjects\Easycode\frontend\vite.config.js
- D:\PycharmProjects\Easycode\frontend\.vs\VSWorkspaceState.json
- D:\PycharmProjects\Easycode\frontend\src\App.vue
- D:\PycharmProjects\Easycode\frontend\src\main.js
- D:\PycharmProjects\Easycode\frontend\src\api\blueprintApi.js
- D:\PycharmProjects\Easycode\frontend\src\api\visionApi.js
- D:\PycharmProjects\Easycode\frontend\src\api\workspaceApi.js
- D:\PycharmProjects\Easycode\frontend\src\assets\theme.css
- D:\PycharmProjects\Easycode\frontend\src\components\AppFooter.vue
- D:\PycharmProjects\Easycode\frontend\src\components\AppHeader.vue
- D:\PycharmProjects\Easycode\frontend\src\components\FileBrowser.vue
- D:\PycharmProjects\Easycode\frontend\src\components\PanelContainer.vue
- D:\PycharmProjects\Easycode\frontend\src\components\PanelSettingsDialog.vue
- D:\PycharmProjects\Easycode\frontend\src\components\ParamRenderer.vue
- D:\PycharmProjects\Easycode\frontend\src\components\ScreenshotTool.vue
- D:\PycharmProjects\Easycode\frontend\src\components\TaskGroupNode.vue
- D:\PycharmProjects\Easycode\frontend\src\components\WorkflowCanvas.vue
- D:\PycharmProjects\Easycode\frontend\src\components\canvas\CanvasLogPanel.vue
- D:\PycharmProjects\Easycode\frontend\src\components\conditions\ConditionDialog.vue
- D:\PycharmProjects\Easycode\frontend\src\components\conditions\conditionSchemas.js
- D:\PycharmProjects\Easycode\frontend\src\components\conditions\index.js
- D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlConditionList.vue
- D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlCoordPicker.vue
- D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlDict.vue
- D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlFileHover.vue
- D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlNumber.vue
- D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlRadioGroup.vue
- D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlSelect.vue
- D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlSlider.vue
- D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlString.vue
- D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlSwitch.vue
- D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlWindowSelect.vue
- D:\PycharmProjects\Easycode\frontend\src\components\controls\Size2Control.vue
- D:\PycharmProjects\Easycode\frontend\src\components\controls\VariableInputControl.vue
- D:\PycharmProjects\Easycode\frontend\src\components\inspector\WorkflowInspector.vue
- D:\PycharmProjects\Easycode\frontend\src\components\inspector\panels\BatchInspectorPanel.vue
- D:\PycharmProjects\Easycode\frontend\src\components\inspector\panels\GroupInspectorPanel.vue
- D:\PycharmProjects\Easycode\frontend\src\components\inspector\panels\NodeInspectorPanel.vue
- D:\PycharmProjects\Easycode\frontend\src\components\panels\GlobalVariablesPanel.vue
- D:\PycharmProjects\Easycode\frontend\src\components\panels\LogPanel.vue
- D:\PycharmProjects\Easycode\frontend\src\components\panels\NodeEditorPanel.vue
- D:\PycharmProjects\Easycode\frontend\src\components\panels\NodeListPanel.vue
- D:\PycharmProjects\Easycode\frontend\src\components\panels\PluginMarketPanel.vue
- D:\PycharmProjects\Easycode\frontend\src\components\panels\ProjectExplorerPanel.vue
- D:\PycharmProjects\Easycode\frontend\src\components\panels\TaskListPanel.vue
- D:\PycharmProjects\Easycode\frontend\src\components\shell\ActivityBar.vue
- D:\PycharmProjects\Easycode\frontend\src\components\shell\TopMenuBar.vue
- D:\PycharmProjects\Easycode\frontend\src\composables\useCanvasDrag.js
- D:\PycharmProjects\Easycode\frontend\src\composables\useCanvasEdges.js
- D:\PycharmProjects\Easycode\frontend\src\composables\useCanvasViewport.js
- D:\PycharmProjects\Easycode\frontend\src\config\panelsConfig.js
- D:\PycharmProjects\Easycode\frontend\src\layouts\IdeLayout.vue
- D:\PycharmProjects\Easycode\frontend\src\stores\index.js
- D:\PycharmProjects\Easycode\frontend\src\utils\gridRouter.js
- D:\PycharmProjects\Easycode\frontend\src\utils\logger.js

## File: D:\PycharmProjects\Easycode\frontend\index.html

- Extension: .html
- Language: html
- Size: 329 bytes
- Created: 2026-07-28 20:03:07
- Modified: 2026-07-28 20:02:33

### Code

```html
 1 | <!DOCTYPE html>
 2 | <html lang="">
 3 |   <head>
 4 |     <meta charset="UTF-8">
 5 |     <link rel="icon" href="/favicon.ico">
 6 |     <meta name="viewport" content="width=device-width, initial-scale=1.0">
 7 |     <title>Vite App</title>
 8 |   </head>
 9 |   <body>
10 |     <div id="app"></div>
11 |     <script type="module" src="/src/main.js"></script>
12 |   </body>
13 | </html>
```

## File: D:\PycharmProjects\Easycode\frontend\jsconfig.json

- Extension: .json
- Language: json
- Size: 115 bytes
- Created: 2026-07-28 20:03:07
- Modified: 2026-07-28 20:36:11

### Code

```json
1 | {
2 |   "compilerOptions": {
3 |     "paths": {
4 |       "@/*": ["./src/*"]
5 |     }
6 |   },
7 |   "exclude": ["node_modules", "dist"]
8 | }
```

## File: D:\PycharmProjects\Easycode\frontend\package-lock.json

- Extension: .json
- Language: json
- Size: 65695 bytes
- Created: 2026-07-28 21:11:44
- Modified: 2026-08-06 12:31:56

### Code

```json
   1 | {
   2 |   "name": "frontend",
   3 |   "version": "0.0.0",
   4 |   "lockfileVersion": 3,
   5 |   "requires": true,
   6 |   "packages": {
   7 |     "": {
   8 |       "name": "frontend",
   9 |       "version": "0.0.0",
  10 |       "dependencies": {
  11 |         "@element-plus/icons-vue": "^2.3.2",
  12 |         "axios": "^1.7.0",
  13 |         "element-plus": "^2.8.0",
  14 |         "lucide-vue-next": "^0.577.0",
  15 |         "pathfinding": "^0.4.18",
  16 |         "pinia": "^4.0.2",
  17 |         "splitpanes": "^4.1.2",
  18 |         "vue": "^3.4.0",
  19 |         "vuedraggable": "^4.1.0"
  20 |       },
  21 |       "devDependencies": {
  22 |         "@vitejs/plugin-vue": "^5.0.4",
  23 |         "@vue/devtools-api": "^8.2.1",
  24 |         "vite": "^5.0.0"
  25 |       }
  26 |     },
  27 |     "node_modules/@babel/helper-string-parser": {
  28 |       "version": "7.29.7",
  29 |       "resolved": "https://registry.npmmirror.com/@babel/helper-string-parser/-/helper-string-parser-7.29.7.tgz",
  30 |       "integrity": "sha512-Pb5ijPrZ89GDH8223L4UP8i6QApWxs04RbPQJTeWDV0/keR2E36MeKnyr6LYmUUvqRRI+Iv87SuF1W6ErINzYw==",
  31 |       "license": "MIT",
  32 |       "engines": {
  33 |         "node": ">=6.9.0"
  34 |       }
  35 |     },
  36 |     "node_modules/@babel/helper-validator-identifier": {
  37 |       "version": "7.29.7",
  38 |       "resolved": "https://registry.npmmirror.com/@babel/helper-validator-identifier/-/helper-validator-identifier-7.29.7.tgz",
  39 |       "integrity": "sha512-qehxGkRj55h/ff8EMaJ+cYhyaKlHIxqYDn682wQD7RNp9UujOQsHog2uS0r2vzr4pW+sXf90NeeayjcNaX3fFg==",
  40 |       "license": "MIT",
  41 |       "engines": {
  42 |         "node": ">=6.9.0"
  43 |       }
  44 |     },
  45 |     "node_modules/@babel/parser": {
  46 |       "version": "7.29.7",
  47 |       "resolved": "https://registry.npmmirror.com/@babel/parser/-/parser-7.29.7.tgz",
  48 |       "integrity": "sha512-hnORnjP/1P/zFEndoeX+n+t1RwWRJiJpM/jO7FW32Kn9r5+sJB2JWOdYo4L6k78j15eCwY3Gm/7364B1EMwtNg==",
  49 |       "license": "MIT",
  50 |       "dependencies": {
  51 |         "@babel/types": "^7.29.7"
  52 |       },
  53 |       "bin": {
  54 |         "parser": "bin/babel-parser.js"
  55 |       },
  56 |       "engines": {
  57 |         "node": ">=6.0.0"
  58 |       }
  59 |     },
  60 |     "node_modules/@babel/types": {
  61 |       "version": "7.29.7",
  62 |       "resolved": "https://registry.npmmirror.com/@babel/types/-/types-7.29.7.tgz",
  63 |       "integrity": "sha512-4zBIxpPzowiZpusoFkyGVwakdRJUyuH5PxQ/PrqghfdFWWasvnCdPfQXHrenDai+gyLARulZjZowCOj6fjT4pA==",
  64 |       "license": "MIT",
  65 |       "dependencies": {
  66 |         "@babel/helper-string-parser": "^7.29.7",
  67 |         "@babel/helper-validator-identifier": "^7.29.7"
  68 |       },
  69 |       "engines": {
  70 |         "node": ">=6.9.0"
  71 |       }
  72 |     },
  73 |     "node_modules/@ctrl/tinycolor": {
  74 |       "version": "4.2.0",
  75 |       "resolved": "https://registry.npmmirror.com/@ctrl/tinycolor/-/tinycolor-4.2.0.tgz",
  76 |       "integrity": "sha512-kzyuwOAQnXJNLS9PSyrk0CWk35nWJW/zl/6KvnTBMFK65gm7U1/Z5BqjxeapjZCIhQcM/DsrEmcbRwDyXyXK4A==",
  77 |       "license": "MIT",
  78 |       "engines": {
  79 |         "node": ">=14"
  80 |       }
  81 |     },
  82 |     "node_modules/@element-plus/icons-vue": {
  83 |       "version": "2.3.2",
  84 |       "resolved": "https://registry.npmmirror.com/@element-plus/icons-vue/-/icons-vue-2.3.2.tgz",
  85 |       "integrity": "sha512-OzIuTaIfC8QXEPmJvB4Y4kw34rSXdCJzxcD1kFStBvr8bK6X1zQAYDo0CNMjojnfTqRQCJ0I7prlErcoRiET2A==",
  86 |       "license": "MIT",
  87 |       "peerDependencies": {
  88 |         "vue": "^3.2.0"
  89 |       }
  90 |     },
  91 |     "node_modules/@esbuild/aix-ppc64": {
  92 |       "version": "0.21.5",
  93 |       "resolved": "https://registry.npmmirror.com/@esbuild/aix-ppc64/-/aix-ppc64-0.21.5.tgz",
  94 |       "integrity": "sha512-1SDgH6ZSPTlggy1yI6+Dbkiz8xzpHJEVAlF/AM1tHPLsf5STom9rwtjE4hKAF20FfXXNTFqEYXyJNWh1GiZedQ==",
  95 |       "cpu": [
  96 |         "ppc64"
  97 |       ],
  98 |       "dev": true,
  99 |       "license": "MIT",
 100 |       "optional": true,
 101 |       "os": [
 102 |         "aix"
 103 |       ],
 104 |       "engines": {
 105 |         "node": ">=12"
 106 |       }
 107 |     },
 108 |     "node_modules/@esbuild/android-arm": {
 109 |       "version": "0.21.5",
 110 |       "resolved": "https://registry.npmmirror.com/@esbuild/android-arm/-/android-arm-0.21.5.tgz",
 111 |       "integrity": "sha512-vCPvzSjpPHEi1siZdlvAlsPxXl7WbOVUBBAowWug4rJHb68Ox8KualB+1ocNvT5fjv6wpkX6o/iEpbDrf68zcg==",
 112 |       "cpu": [
 113 |         "arm"
 114 |       ],
 115 |       "dev": true,
 116 |       "license": "MIT",
 117 |       "optional": true,
 118 |       "os": [
 119 |         "android"
 120 |       ],
 121 |       "engines": {
 122 |         "node": ">=12"
 123 |       }
 124 |     },
 125 |     "node_modules/@esbuild/android-arm64": {
 126 |       "version": "0.21.5",
 127 |       "resolved": "https://registry.npmmirror.com/@esbuild/android-arm64/-/android-arm64-0.21.5.tgz",
 128 |       "integrity": "sha512-c0uX9VAUBQ7dTDCjq+wdyGLowMdtR/GoC2U5IYk/7D1H1JYC0qseD7+11iMP2mRLN9RcCMRcjC4YMclCzGwS/A==",
 129 |       "cpu": [
 130 |         "arm64"
 131 |       ],
 132 |       "dev": true,
 133 |       "license": "MIT",
 134 |       "optional": true,
 135 |       "os": [
 136 |         "android"
 137 |       ],
 138 |       "engines": {
 139 |         "node": ">=12"
 140 |       }
 141 |     },
 142 |     "node_modules/@esbuild/android-x64": {
 143 |       "version": "0.21.5",
 144 |       "resolved": "https://registry.npmmirror.com/@esbuild/android-x64/-/android-x64-0.21.5.tgz",
 145 |       "integrity": "sha512-D7aPRUUNHRBwHxzxRvp856rjUHRFW1SdQATKXH2hqA0kAZb1hKmi02OpYRacl0TxIGz/ZmXWlbZgjwWYaCakTA==",
 146 |       "cpu": [
 147 |         "x64"
 148 |       ],
 149 |       "dev": true,
 150 |       "license": "MIT",
 151 |       "optional": true,
 152 |       "os": [
 153 |         "android"
 154 |       ],
 155 |       "engines": {
 156 |         "node": ">=12"
 157 |       }
 158 |     },
 159 |     "node_modules/@esbuild/darwin-arm64": {
 160 |       "version": "0.21.5",
 161 |       "resolved": "https://registry.npmmirror.com/@esbuild/darwin-arm64/-/darwin-arm64-0.21.5.tgz",
 162 |       "integrity": "sha512-DwqXqZyuk5AiWWf3UfLiRDJ5EDd49zg6O9wclZ7kUMv2WRFr4HKjXp/5t8JZ11QbQfUS6/cRCKGwYhtNAY88kQ==",
 163 |       "cpu": [
 164 |         "arm64"
 165 |       ],
 166 |       "dev": true,
 167 |       "license": "MIT",
 168 |       "optional": true,
 169 |       "os": [
 170 |         "darwin"
 171 |       ],
 172 |       "engines": {
 173 |         "node": ">=12"
 174 |       }
 175 |     },
 176 |     "node_modules/@esbuild/darwin-x64": {
 177 |       "version": "0.21.5",
 178 |       "resolved": "https://registry.npmmirror.com/@esbuild/darwin-x64/-/darwin-x64-0.21.5.tgz",
 179 |       "integrity": "sha512-se/JjF8NlmKVG4kNIuyWMV/22ZaerB+qaSi5MdrXtd6R08kvs2qCN4C09miupktDitvh8jRFflwGFBQcxZRjbw==",
 180 |       "cpu": [
 181 |         "x64"
 182 |       ],
 183 |       "dev": true,
 184 |       "license": "MIT",
 185 |       "optional": true,
 186 |       "os": [
 187 |         "darwin"
 188 |       ],
 189 |       "engines": {
 190 |         "node": ">=12"
 191 |       }
 192 |     },
 193 |     "node_modules/@esbuild/freebsd-arm64": {
 194 |       "version": "0.21.5",
 195 |       "resolved": "https://registry.npmmirror.com/@esbuild/freebsd-arm64/-/freebsd-arm64-0.21.5.tgz",
 196 |       "integrity": "sha512-5JcRxxRDUJLX8JXp/wcBCy3pENnCgBR9bN6JsY4OmhfUtIHe3ZW0mawA7+RDAcMLrMIZaf03NlQiX9DGyB8h4g==",
 197 |       "cpu": [
 198 |         "arm64"
 199 |       ],
 200 |       "dev": true,
 201 |       "license": "MIT",
 202 |       "optional": true,
 203 |       "os": [
 204 |         "freebsd"
 205 |       ],
 206 |       "engines": {
 207 |         "node": ">=12"
 208 |       }
 209 |     },
 210 |     "node_modules/@esbuild/freebsd-x64": {
 211 |       "version": "0.21.5",
 212 |       "resolved": "https://registry.npmmirror.com/@esbuild/freebsd-x64/-/freebsd-x64-0.21.5.tgz",
 213 |       "integrity": "sha512-J95kNBj1zkbMXtHVH29bBriQygMXqoVQOQYA+ISs0/2l3T9/kj42ow2mpqerRBxDJnmkUDCaQT/dfNXWX/ZZCQ==",
 214 |       "cpu": [
 215 |         "x64"
 216 |       ],
 217 |       "dev": true,
 218 |       "license": "MIT",
 219 |       "optional": true,
 220 |       "os": [
 221 |         "freebsd"
 222 |       ],
 223 |       "engines": {
 224 |         "node": ">=12"
 225 |       }
 226 |     },
 227 |     "node_modules/@esbuild/linux-arm": {
 228 |       "version": "0.21.5",
 229 |       "resolved": "https://registry.npmmirror.com/@esbuild/linux-arm/-/linux-arm-0.21.5.tgz",
 230 |       "integrity": "sha512-bPb5AHZtbeNGjCKVZ9UGqGwo8EUu4cLq68E95A53KlxAPRmUyYv2D6F0uUI65XisGOL1hBP5mTronbgo+0bFcA==",
 231 |       "cpu": [
 232 |         "arm"
 233 |       ],
 234 |       "dev": true,
 235 |       "license": "MIT",
 236 |       "optional": true,
 237 |       "os": [
 238 |         "linux"
 239 |       ],
 240 |       "engines": {
 241 |         "node": ">=12"
 242 |       }
 243 |     },
 244 |     "node_modules/@esbuild/linux-arm64": {
 245 |       "version": "0.21.5",
 246 |       "resolved": "https://registry.npmmirror.com/@esbuild/linux-arm64/-/linux-arm64-0.21.5.tgz",
 247 |       "integrity": "sha512-ibKvmyYzKsBeX8d8I7MH/TMfWDXBF3db4qM6sy+7re0YXya+K1cem3on9XgdT2EQGMu4hQyZhan7TeQ8XkGp4Q==",
 248 |       "cpu": [
 249 |         "arm64"
 250 |       ],
 251 |       "dev": true,
 252 |       "license": "MIT",
 253 |       "optional": true,
 254 |       "os": [
 255 |         "linux"
 256 |       ],
 257 |       "engines": {
 258 |         "node": ">=12"
 259 |       }
 260 |     },
 261 |     "node_modules/@esbuild/linux-ia32": {
 262 |       "version": "0.21.5",
 263 |       "resolved": "https://registry.npmmirror.com/@esbuild/linux-ia32/-/linux-ia32-0.21.5.tgz",
 264 |       "integrity": "sha512-YvjXDqLRqPDl2dvRODYmmhz4rPeVKYvppfGYKSNGdyZkA01046pLWyRKKI3ax8fbJoK5QbxblURkwK/MWY18Tg==",
 265 |       "cpu": [
 266 |         "ia32"
 267 |       ],
 268 |       "dev": true,
 269 |       "license": "MIT",
 270 |       "optional": true,
 271 |       "os": [
 272 |         "linux"
 273 |       ],
 274 |       "engines": {
 275 |         "node": ">=12"
 276 |       }
 277 |     },
 278 |     "node_modules/@esbuild/linux-loong64": {
 279 |       "version": "0.21.5",
 280 |       "resolved": "https://registry.npmmirror.com/@esbuild/linux-loong64/-/linux-loong64-0.21.5.tgz",
 281 |       "integrity": "sha512-uHf1BmMG8qEvzdrzAqg2SIG/02+4/DHB6a9Kbya0XDvwDEKCoC8ZRWI5JJvNdUjtciBGFQ5PuBlpEOXQj+JQSg==",
 282 |       "cpu": [
 283 |         "loong64"
 284 |       ],
 285 |       "dev": true,
 286 |       "license": "MIT",
 287 |       "optional": true,
 288 |       "os": [
 289 |         "linux"
 290 |       ],
 291 |       "engines": {
 292 |         "node": ">=12"
 293 |       }
 294 |     },
 295 |     "node_modules/@esbuild/linux-mips64el": {
 296 |       "version": "0.21.5",
 297 |       "resolved": "https://registry.npmmirror.com/@esbuild/linux-mips64el/-/linux-mips64el-0.21.5.tgz",
 298 |       "integrity": "sha512-IajOmO+KJK23bj52dFSNCMsz1QP1DqM6cwLUv3W1QwyxkyIWecfafnI555fvSGqEKwjMXVLokcV5ygHW5b3Jbg==",
 299 |       "cpu": [
 300 |         "mips64el"
 301 |       ],
 302 |       "dev": true,
 303 |       "license": "MIT",
 304 |       "optional": true,
 305 |       "os": [
 306 |         "linux"
 307 |       ],
 308 |       "engines": {
 309 |         "node": ">=12"
 310 |       }
 311 |     },
 312 |     "node_modules/@esbuild/linux-ppc64": {
 313 |       "version": "0.21.5",
 314 |       "resolved": "https://registry.npmmirror.com/@esbuild/linux-ppc64/-/linux-ppc64-0.21.5.tgz",
 315 |       "integrity": "sha512-1hHV/Z4OEfMwpLO8rp7CvlhBDnjsC3CttJXIhBi+5Aj5r+MBvy4egg7wCbe//hSsT+RvDAG7s81tAvpL2XAE4w==",
 316 |       "cpu": [
 317 |         "ppc64"
 318 |       ],
 319 |       "dev": true,
 320 |       "license": "MIT",
 321 |       "optional": true,
 322 |       "os": [
 323 |         "linux"
 324 |       ],
 325 |       "engines": {
 326 |         "node": ">=12"
 327 |       }
 328 |     },
 329 |     "node_modules/@esbuild/linux-riscv64": {
 330 |       "version": "0.21.5",
 331 |       "resolved": "https://registry.npmmirror.com/@esbuild/linux-riscv64/-/linux-riscv64-0.21.5.tgz",
 332 |       "integrity": "sha512-2HdXDMd9GMgTGrPWnJzP2ALSokE/0O5HhTUvWIbD3YdjME8JwvSCnNGBnTThKGEB91OZhzrJ4qIIxk/SBmyDDA==",
 333 |       "cpu": [
 334 |         "riscv64"
 335 |       ],
 336 |       "dev": true,
 337 |       "license": "MIT",
 338 |       "optional": true,
 339 |       "os": [
 340 |         "linux"
 341 |       ],
 342 |       "engines": {
 343 |         "node": ">=12"
 344 |       }
 345 |     },
 346 |     "node_modules/@esbuild/linux-s390x": {
 347 |       "version": "0.21.5",
 348 |       "resolved": "https://registry.npmmirror.com/@esbuild/linux-s390x/-/linux-s390x-0.21.5.tgz",
 349 |       "integrity": "sha512-zus5sxzqBJD3eXxwvjN1yQkRepANgxE9lgOW2qLnmr8ikMTphkjgXu1HR01K4FJg8h1kEEDAqDcZQtbrRnB41A==",
 350 |       "cpu": [
 351 |         "s390x"
 352 |       ],
 353 |       "dev": true,
 354 |       "license": "MIT",
 355 |       "optional": true,
 356 |       "os": [
 357 |         "linux"
 358 |       ],
 359 |       "engines": {
 360 |         "node": ">=12"
 361 |       }
 362 |     },
 363 |     "node_modules/@esbuild/linux-x64": {
 364 |       "version": "0.21.5",
 365 |       "resolved": "https://registry.npmmirror.com/@esbuild/linux-x64/-/linux-x64-0.21.5.tgz",
 366 |       "integrity": "sha512-1rYdTpyv03iycF1+BhzrzQJCdOuAOtaqHTWJZCWvijKD2N5Xu0TtVC8/+1faWqcP9iBCWOmjmhoH94dH82BxPQ==",
 367 |       "cpu": [
 368 |         "x64"
 369 |       ],
 370 |       "dev": true,
 371 |       "license": "MIT",
 372 |       "optional": true,
 373 |       "os": [
 374 |         "linux"
 375 |       ],
 376 |       "engines": {
 377 |         "node": ">=12"
 378 |       }
 379 |     },
 380 |     "node_modules/@esbuild/netbsd-x64": {
 381 |       "version": "0.21.5",
 382 |       "resolved": "https://registry.npmmirror.com/@esbuild/netbsd-x64/-/netbsd-x64-0.21.5.tgz",
 383 |       "integrity": "sha512-Woi2MXzXjMULccIwMnLciyZH4nCIMpWQAs049KEeMvOcNADVxo0UBIQPfSmxB3CWKedngg7sWZdLvLczpe0tLg==",
 384 |       "cpu": [
 385 |         "x64"
 386 |       ],
 387 |       "dev": true,
 388 |       "license": "MIT",
 389 |       "optional": true,
 390 |       "os": [
 391 |         "netbsd"
 392 |       ],
 393 |       "engines": {
 394 |         "node": ">=12"
 395 |       }
 396 |     },
 397 |     "node_modules/@esbuild/openbsd-x64": {
 398 |       "version": "0.21.5",
 399 |       "resolved": "https://registry.npmmirror.com/@esbuild/openbsd-x64/-/openbsd-x64-0.21.5.tgz",
 400 |       "integrity": "sha512-HLNNw99xsvx12lFBUwoT8EVCsSvRNDVxNpjZ7bPn947b8gJPzeHWyNVhFsaerc0n3TsbOINvRP2byTZ5LKezow==",
 401 |       "cpu": [
 402 |         "x64"
 403 |       ],
 404 |       "dev": true,
 405 |       "license": "MIT",
 406 |       "optional": true,
 407 |       "os": [
 408 |         "openbsd"
 409 |       ],
 410 |       "engines": {
 411 |         "node": ">=12"
 412 |       }
 413 |     },
 414 |     "node_modules/@esbuild/sunos-x64": {
 415 |       "version": "0.21.5",
 416 |       "resolved": "https://registry.npmmirror.com/@esbuild/sunos-x64/-/sunos-x64-0.21.5.tgz",
 417 |       "integrity": "sha512-6+gjmFpfy0BHU5Tpptkuh8+uw3mnrvgs+dSPQXQOv3ekbordwnzTVEb4qnIvQcYXq6gzkyTnoZ9dZG+D4garKg==",
 418 |       "cpu": [
 419 |         "x64"
 420 |       ],
 421 |       "dev": true,
 422 |       "license": "MIT",
 423 |       "optional": true,
 424 |       "os": [
 425 |         "sunos"
 426 |       ],
 427 |       "engines": {
 428 |         "node": ">=12"
 429 |       }
 430 |     },
 431 |     "node_modules/@esbuild/win32-arm64": {
 432 |       "version": "0.21.5",
 433 |       "resolved": "https://registry.npmmirror.com/@esbuild/win32-arm64/-/win32-arm64-0.21.5.tgz",
 434 |       "integrity": "sha512-Z0gOTd75VvXqyq7nsl93zwahcTROgqvuAcYDUr+vOv8uHhNSKROyU961kgtCD1e95IqPKSQKH7tBTslnS3tA8A==",
 435 |       "cpu": [
 436 |         "arm64"
 437 |       ],
 438 |       "dev": true,
 439 |       "license": "MIT",
 440 |       "optional": true,
 441 |       "os": [
 442 |         "win32"
 443 |       ],
 444 |       "engines": {
 445 |         "node": ">=12"
 446 |       }
 447 |     },
 448 |     "node_modules/@esbuild/win32-ia32": {
 449 |       "version": "0.21.5",
 450 |       "resolved": "https://registry.npmmirror.com/@esbuild/win32-ia32/-/win32-ia32-0.21.5.tgz",
 451 |       "integrity": "sha512-SWXFF1CL2RVNMaVs+BBClwtfZSvDgtL//G/smwAc5oVK/UPu2Gu9tIaRgFmYFFKrmg3SyAjSrElf0TiJ1v8fYA==",
 452 |       "cpu": [
 453 |         "ia32"
 454 |       ],
 455 |       "dev": true,
 456 |       "license": "MIT",
 457 |       "optional": true,
 458 |       "os": [
 459 |         "win32"
 460 |       ],
 461 |       "engines": {
 462 |         "node": ">=12"
 463 |       }
 464 |     },
 465 |     "node_modules/@esbuild/win32-x64": {
 466 |       "version": "0.21.5",
 467 |       "resolved": "https://registry.npmmirror.com/@esbuild/win32-x64/-/win32-x64-0.21.5.tgz",
 468 |       "integrity": "sha512-tQd/1efJuzPC6rCFwEvLtci/xNFcTZknmXs98FYDfGE4wP9ClFV98nyKrzJKVPMhdDnjzLhdUyMX4PsQAPjwIw==",
 469 |       "cpu": [
 470 |         "x64"
 471 |       ],
 472 |       "dev": true,
 473 |       "license": "MIT",
 474 |       "optional": true,
 475 |       "os": [
 476 |         "win32"
 477 |       ],
 478 |       "engines": {
 479 |         "node": ">=12"
 480 |       }
 481 |     },
 482 |     "node_modules/@floating-ui/core": {
 483 |       "version": "1.8.0",
 484 |       "resolved": "https://registry.npmmirror.com/@floating-ui/core/-/core-1.8.0.tgz",
 485 |       "integrity": "sha512-0CIZ5itps/8x7BG8dEIhs53BvCUH2PCoogtakwRTut+Arm58sJooJ0AuZhLw2HJYIR5cMLNPBSS728sPho2khQ==",
 486 |       "license": "MIT",
 487 |       "dependencies": {
 488 |         "@floating-ui/utils": "^0.2.12"
 489 |       }
 490 |     },
 491 |     "node_modules/@floating-ui/dom": {
 492 |       "version": "1.8.0",
 493 |       "resolved": "https://registry.npmmirror.com/@floating-ui/dom/-/dom-1.8.0.tgz",
 494 |       "integrity": "sha512-yXSrzeHZBTZadLOlfyhCkJHNeLJnHRnRInwdZ40L7ZiaAtrBwoYlsDrX3v5zB1Utk7CLfzcOVnVVWoXEky7Ceg==",
 495 |       "license": "MIT",
 496 |       "dependencies": {
 497 |         "@floating-ui/core": "^1.8.0",
 498 |         "@floating-ui/utils": "^0.2.12"
 499 |       }
 500 |     },
 501 |     "node_modules/@floating-ui/utils": {
 502 |       "version": "0.2.12",
 503 |       "resolved": "https://registry.npmmirror.com/@floating-ui/utils/-/utils-0.2.12.tgz",
 504 |       "integrity": "sha512-HpCo8tmWzLVad5s2d19EhAz5zqrrQ6s69qd6moPMQvkOuSwDT1YgRfWSVuc4ennqrgv3OHppiOGMQ7oC13yIww==",
 505 |       "license": "MIT"
 506 |     },
 507 |     "node_modules/@jridgewell/sourcemap-codec": {
 508 |       "version": "1.5.5",
 509 |       "resolved": "https://registry.npmmirror.com/@jridgewell/sourcemap-codec/-/sourcemap-codec-1.5.5.tgz",
 510 |       "integrity": "sha512-cYQ9310grqxueWbl+WuIUIaiUaDcj7WOq5fVhEljNVgRfOUhY9fy2zTvfoqWsnebh8Sl70VScFbICvJnLKB0Og==",
 511 |       "license": "MIT"
 512 |     },
 513 |     "node_modules/@popperjs/core": {
 514 |       "name": "@sxzz/popperjs-es",
 515 |       "version": "2.11.8",
 516 |       "resolved": "https://registry.npmmirror.com/@sxzz/popperjs-es/-/popperjs-es-2.11.8.tgz",
 517 |       "integrity": "sha512-wOwESXvvED3S8xBmcPWHs2dUuzrE4XiZeFu7e1hROIJkm02a49N120pmOXxY33sBb6hArItm5W5tcg1cBtV+HQ==",
 518 |       "license": "MIT",
 519 |       "funding": {
 520 |         "type": "opencollective",
 521 |         "url": "https://opencollective.com/popperjs"
 522 |       }
 523 |     },
 524 |     "node_modules/@rollup/rollup-android-arm-eabi": {
 525 |       "version": "4.62.3",
 526 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-android-arm-eabi/-/rollup-android-arm-eabi-4.62.3.tgz",
 527 |       "integrity": "sha512-c0wdcekXtQvvn5Tsrk/+op/gUArrbWaFduBnTLP2l1cKLSQs4diMWjJw3m6A0DdzT8dAAX95KpkJ3qynCePbmw==",
 528 |       "cpu": [
 529 |         "arm"
 530 |       ],
 531 |       "dev": true,
 532 |       "license": "MIT",
 533 |       "optional": true,
 534 |       "os": [
 535 |         "android"
 536 |       ]
 537 |     },
 538 |     "node_modules/@rollup/rollup-android-arm64": {
 539 |       "version": "4.62.3",
 540 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-android-arm64/-/rollup-android-arm64-4.62.3.tgz",
 541 |       "integrity": "sha512-3YjElDdWN+qXAFbJ/CzPV+0wspLqh54k/I6GfdYtEJRqg7buSgc1yPM3B+93j1M4neobtkATHZTmxK2AMVGfnA==",
 542 |       "cpu": [
 543 |         "arm64"
 544 |       ],
 545 |       "dev": true,
 546 |       "license": "MIT",
 547 |       "optional": true,
 548 |       "os": [
 549 |         "android"
 550 |       ]
 551 |     },
 552 |     "node_modules/@rollup/rollup-darwin-arm64": {
 553 |       "version": "4.62.3",
 554 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-darwin-arm64/-/rollup-darwin-arm64-4.62.3.tgz",
 555 |       "integrity": "sha512-Pch2pFNOxxz1hTjypIdPyRTR6riiwRl84+VcN9djS680fw+Co1nAJINrdpqp7KV0NvyuU8ilZXZCjd7ykJl1GQ==",
 556 |       "cpu": [
 557 |         "arm64"
 558 |       ],
 559 |       "dev": true,
 560 |       "license": "MIT",
 561 |       "optional": true,
 562 |       "os": [
 563 |         "darwin"
 564 |       ]
 565 |     },
 566 |     "node_modules/@rollup/rollup-darwin-x64": {
 567 |       "version": "4.62.3",
 568 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-darwin-x64/-/rollup-darwin-x64-4.62.3.tgz",
 569 |       "integrity": "sha512-LEuncFUHFiF8t4yZVZvvZA1wk0pjAscRnsrn1EfTEmN4HXotBi2YtcnLRyaK6UbuczW7xZS5ES+81Rdz8Z0T6g==",
 570 |       "cpu": [
 571 |         "x64"
 572 |       ],
 573 |       "dev": true,
 574 |       "license": "MIT",
 575 |       "optional": true,
 576 |       "os": [
 577 |         "darwin"
 578 |       ]
 579 |     },
 580 |     "node_modules/@rollup/rollup-freebsd-arm64": {
 581 |       "version": "4.62.3",
 582 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-freebsd-arm64/-/rollup-freebsd-arm64-4.62.3.tgz",
 583 |       "integrity": "sha512-zvBUvsQUpOWALdDsk6qbS8bXf2VxmPisuudNDrY7x0p0jBdsoZl8HsHczIOgkQiZldmcacMKtBzpoGVNeIe2bQ==",
 584 |       "cpu": [
 585 |         "arm64"
 586 |       ],
 587 |       "dev": true,
 588 |       "license": "MIT",
 589 |       "optional": true,
 590 |       "os": [
 591 |         "freebsd"
 592 |       ]
 593 |     },
 594 |     "node_modules/@rollup/rollup-freebsd-x64": {
 595 |       "version": "4.62.3",
 596 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-freebsd-x64/-/rollup-freebsd-x64-4.62.3.tgz",
 597 |       "integrity": "sha512-C2KmNrcSem/AMg984H/dev+si0lieQGdXdR/lYGJnuumXnFb9Y7QdiI62obFdLlxRYLBv4P0eUVIDbD4c1vVvw==",
 598 |       "cpu": [
 599 |         "x64"
 600 |       ],
 601 |       "dev": true,
 602 |       "license": "MIT",
 603 |       "optional": true,
 604 |       "os": [
 605 |         "freebsd"
 606 |       ]
 607 |     },
 608 |     "node_modules/@rollup/rollup-linux-arm-gnueabihf": {
 609 |       "version": "4.62.3",
 610 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-arm-gnueabihf/-/rollup-linux-arm-gnueabihf-4.62.3.tgz",
 611 |       "integrity": "sha512-ggXnsTAEzNQx74XpunRsiZ9aBZDsI7XIa0hm2nzR9f4WzH5/f/d73ZSDaC5ejJ8YLY4NW+V3wr0tjOaeCq8hqA==",
 612 |       "cpu": [
 613 |         "arm"
 614 |       ],
 615 |       "dev": true,
 616 |       "libc": [
 617 |         "glibc"
 618 |       ],
 619 |       "license": "MIT",
 620 |       "optional": true,
 621 |       "os": [
 622 |         "linux"
 623 |       ]
 624 |     },
 625 |     "node_modules/@rollup/rollup-linux-arm-musleabihf": {
 626 |       "version": "4.62.3",
 627 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-arm-musleabihf/-/rollup-linux-arm-musleabihf-4.62.3.tgz",
 628 |       "integrity": "sha512-2vng+FlzNUhKZxtej3IUqJgbZoQk2M/dwQM20+ULV0R/E/8tr9/P6uEf2iiGIk4HL0zMKh5Jry7mUHdUOvyGgA==",
 629 |       "cpu": [
 630 |         "arm"
 631 |       ],
 632 |       "dev": true,
 633 |       "libc": [
 634 |         "musl"
 635 |       ],
 636 |       "license": "MIT",
 637 |       "optional": true,
 638 |       "os": [
 639 |         "linux"
 640 |       ]
 641 |     },
 642 |     "node_modules/@rollup/rollup-linux-arm64-gnu": {
 643 |       "version": "4.62.3",
 644 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-arm64-gnu/-/rollup-linux-arm64-gnu-4.62.3.tgz",
 645 |       "integrity": "sha512-LLLFZKt4/Nraf9rxDkhiU8QVgLF4WmCkfr0L4fj0fPfIZFBib0DeiFk1hhaYKd03LFAFJcxHslhDFlNJLylf5Q==",
 646 |       "cpu": [
 647 |         "arm64"
 648 |       ],
 649 |       "dev": true,
 650 |       "libc": [
 651 |         "glibc"
 652 |       ],
 653 |       "license": "MIT",
 654 |       "optional": true,
 655 |       "os": [
 656 |         "linux"
 657 |       ]
 658 |     },
 659 |     "node_modules/@rollup/rollup-linux-arm64-musl": {
 660 |       "version": "4.62.3",
 661 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-arm64-musl/-/rollup-linux-arm64-musl-4.62.3.tgz",
 662 |       "integrity": "sha512-WJkdQCvS9sWNOUBJZfQRKpZGFBztRzcowI+nndmflKgU4XY+3a420FgTOSKTsVqJbnzSxeT4vaJalpOaPo2YCQ==",
 663 |       "cpu": [
 664 |         "arm64"
 665 |       ],
 666 |       "dev": true,
 667 |       "libc": [
 668 |         "musl"
 669 |       ],
 670 |       "license": "MIT",
 671 |       "optional": true,
 672 |       "os": [
 673 |         "linux"
 674 |       ]
 675 |     },
 676 |     "node_modules/@rollup/rollup-linux-loong64-gnu": {
 677 |       "version": "4.62.3",
 678 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-loong64-gnu/-/rollup-linux-loong64-gnu-4.62.3.tgz",
 679 |       "integrity": "sha512-PwHXCCS2n64/1Ot6rP1YEYA02MGYBcQlr8CSZZyrUG2O7NH6NklYmvr9v3Jy+5e/eDeNchc/ukmKJi9LuflMIQ==",
 680 |       "cpu": [
 681 |         "loong64"
 682 |       ],
 683 |       "dev": true,
 684 |       "libc": [
 685 |         "glibc"
 686 |       ],
 687 |       "license": "MIT",
 688 |       "optional": true,
 689 |       "os": [
 690 |         "linux"
 691 |       ]
 692 |     },
 693 |     "node_modules/@rollup/rollup-linux-loong64-musl": {
 694 |       "version": "4.62.3",
 695 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-loong64-musl/-/rollup-linux-loong64-musl-4.62.3.tgz",
 696 |       "integrity": "sha512-vUjxINQu3RC8NZS3ykk1gN65gIz8pAopOq2HXuZhiIxHdx7TFvDG+jgrdSgInu1Eza4/Rfi2VzZgyIgEH4WOaw==",
 697 |       "cpu": [
 698 |         "loong64"
 699 |       ],
 700 |       "dev": true,
 701 |       "libc": [
 702 |         "musl"
 703 |       ],
 704 |       "license": "MIT",
 705 |       "optional": true,
 706 |       "os": [
 707 |         "linux"
 708 |       ]
 709 |     },
 710 |     "node_modules/@rollup/rollup-linux-ppc64-gnu": {
 711 |       "version": "4.62.3",
 712 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-ppc64-gnu/-/rollup-linux-ppc64-gnu-4.62.3.tgz",
 713 |       "integrity": "sha512-wzko4aJ13+0G3kGnviCg5gnXFKd40izKsrf2uOw12US4XqprkDrmwOpeW14aSNa37V8bfPcz5Fkob6LZ3BAPmA==",
 714 |       "cpu": [
 715 |         "ppc64"
 716 |       ],
 717 |       "dev": true,
 718 |       "libc": [
 719 |         "glibc"
 720 |       ],
 721 |       "license": "MIT",
 722 |       "optional": true,
 723 |       "os": [
 724 |         "linux"
 725 |       ]
 726 |     },
 727 |     "node_modules/@rollup/rollup-linux-ppc64-musl": {
 728 |       "version": "4.62.3",
 729 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-ppc64-musl/-/rollup-linux-ppc64-musl-4.62.3.tgz",
 730 |       "integrity": "sha512-8120ue0JUMSwy11stlwnfdX3pPd+WZYGCDBwEHWtIHi6pOpZmsEF5QKB7a/UN+XFdqvobxz98kv8RTqikyCEBw==",
 731 |       "cpu": [
 732 |         "ppc64"
 733 |       ],
 734 |       "dev": true,
 735 |       "libc": [
 736 |         "musl"
 737 |       ],
 738 |       "license": "MIT",
 739 |       "optional": true,
 740 |       "os": [
 741 |         "linux"
 742 |       ]
 743 |     },
 744 |     "node_modules/@rollup/rollup-linux-riscv64-gnu": {
 745 |       "version": "4.62.3",
 746 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-riscv64-gnu/-/rollup-linux-riscv64-gnu-4.62.3.tgz",
 747 |       "integrity": "sha512-XLFHnR3tXMjbOCh2vtVJHmxt+995uJsTERQyseFDRA0xxMxyTZPLa3OIUlyFaO4mF/Lu0FjmWHCuPXJT1n/IOg==",
 748 |       "cpu": [
 749 |         "riscv64"
 750 |       ],
 751 |       "dev": true,
 752 |       "libc": [
 753 |         "glibc"
 754 |       ],
 755 |       "license": "MIT",
 756 |       "optional": true,
 757 |       "os": [
 758 |         "linux"
 759 |       ]
 760 |     },
 761 |     "node_modules/@rollup/rollup-linux-riscv64-musl": {
 762 |       "version": "4.62.3",
 763 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-riscv64-musl/-/rollup-linux-riscv64-musl-4.62.3.tgz",
 764 |       "integrity": "sha512-se6yXvNGMIl0f+RQzyh7XAmia8/9kplQx424wnG2w0C1oi6XgO6Y8otKhdXFHbHs88Ihavzmvh1NWjuovE76BQ==",
 765 |       "cpu": [
 766 |         "riscv64"
 767 |       ],
 768 |       "dev": true,
 769 |       "libc": [
 770 |         "musl"
 771 |       ],
 772 |       "license": "MIT",
 773 |       "optional": true,
 774 |       "os": [
 775 |         "linux"
 776 |       ]
 777 |     },
 778 |     "node_modules/@rollup/rollup-linux-s390x-gnu": {
 779 |       "version": "4.62.3",
 780 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-s390x-gnu/-/rollup-linux-s390x-gnu-4.62.3.tgz",
 781 |       "integrity": "sha512-gNoxRefktVIiGflpONuxWWXZAzIQG++z9qHO3xKwk4WdDMuQja3JHGfE1u0i3PfPDyvhypdk+WrgIJqLhGG7sg==",
 782 |       "cpu": [
 783 |         "s390x"
 784 |       ],
 785 |       "dev": true,
 786 |       "libc": [
 787 |         "glibc"
 788 |       ],
 789 |       "license": "MIT",
 790 |       "optional": true,
 791 |       "os": [
 792 |         "linux"
 793 |       ]
 794 |     },
 795 |     "node_modules/@rollup/rollup-linux-x64-gnu": {
 796 |       "version": "4.62.3",
 797 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-x64-gnu/-/rollup-linux-x64-gnu-4.62.3.tgz",
 798 |       "integrity": "sha512-V4KtWtQfAFMU7+9/A/VDps/VI8CHd3cYz0L8sgJzz8qK7eY7wI4ruFD82UYIYvW9Z4DtlTfhQcsl4XyPHW5uSg==",
 799 |       "cpu": [
 800 |         "x64"
 801 |       ],
 802 |       "dev": true,
 803 |       "libc": [
 804 |         "glibc"
 805 |       ],
 806 |       "license": "MIT",
 807 |       "optional": true,
 808 |       "os": [
 809 |         "linux"
 810 |       ]
 811 |     },
 812 |     "node_modules/@rollup/rollup-linux-x64-musl": {
 813 |       "version": "4.62.3",
 814 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-linux-x64-musl/-/rollup-linux-x64-musl-4.62.3.tgz",
 815 |       "integrity": "sha512-LBx9LYXvj2CBkMkjLdNAWLwH0MLMin7do2VcVo9kVPibGLkY0BQQut2fv7NVqkXqZ/CrAu9LqDHVV1xHCMpCPw==",
 816 |       "cpu": [
 817 |         "x64"
 818 |       ],
 819 |       "dev": true,
 820 |       "libc": [
 821 |         "musl"
 822 |       ],
 823 |       "license": "MIT",
 824 |       "optional": true,
 825 |       "os": [
 826 |         "linux"
 827 |       ]
 828 |     },
 829 |     "node_modules/@rollup/rollup-openbsd-x64": {
 830 |       "version": "4.62.3",
 831 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-openbsd-x64/-/rollup-openbsd-x64-4.62.3.tgz",
 832 |       "integrity": "sha512-ABVf3Q0RCu7NcyCCOZQI0pJ3GuSdfSl8EXcy88QtdceIMIoCUdfhsJChZ64L9zVM2aJHjde1Bhn5uqSRcX9ySA==",
 833 |       "cpu": [
 834 |         "x64"
 835 |       ],
 836 |       "dev": true,
 837 |       "license": "MIT",
 838 |       "optional": true,
 839 |       "os": [
 840 |         "openbsd"
 841 |       ]
 842 |     },
 843 |     "node_modules/@rollup/rollup-openharmony-arm64": {
 844 |       "version": "4.62.3",
 845 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-openharmony-arm64/-/rollup-openharmony-arm64-4.62.3.tgz",
 846 |       "integrity": "sha512-+2Cy/ldweGBLlPIKsQLF8U5N44a0KDdbrk1rAjHOM9M2K+kGdIVjHLmmrZIcx+9Ny3ke/1JomCsDI1ocb11+sg==",
 847 |       "cpu": [
 848 |         "arm64"
 849 |       ],
 850 |       "dev": true,
 851 |       "license": "MIT",
 852 |       "optional": true,
 853 |       "os": [
 854 |         "openharmony"
 855 |       ]
 856 |     },
 857 |     "node_modules/@rollup/rollup-win32-arm64-msvc": {
 858 |       "version": "4.62.3",
 859 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-win32-arm64-msvc/-/rollup-win32-arm64-msvc-4.62.3.tgz",
 860 |       "integrity": "sha512-dtZvzc8BedpSaFNy75x6uiWwAGTH+aZHDtdrqP6qk+WcLJrfti6sGje1ZJ9UxyzDLF23d/mV+PaMwuC0hL7UVA==",
 861 |       "cpu": [
 862 |         "arm64"
 863 |       ],
 864 |       "dev": true,
 865 |       "license": "MIT",
 866 |       "optional": true,
 867 |       "os": [
 868 |         "win32"
 869 |       ]
 870 |     },
 871 |     "node_modules/@rollup/rollup-win32-ia32-msvc": {
 872 |       "version": "4.62.3",
 873 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-win32-ia32-msvc/-/rollup-win32-ia32-msvc-4.62.3.tgz",
 874 |       "integrity": "sha512-Rj8Ra4noo+aYy7sKBggCx0407mws34kAb1ySyWuq5DAtFBQdkSwnsjCgPrhPe9cvgBKZIukpE+CVHvORCS93kQ==",
 875 |       "cpu": [
 876 |         "ia32"
 877 |       ],
 878 |       "dev": true,
 879 |       "license": "MIT",
 880 |       "optional": true,
 881 |       "os": [
 882 |         "win32"
 883 |       ]
 884 |     },
 885 |     "node_modules/@rollup/rollup-win32-x64-gnu": {
 886 |       "version": "4.62.3",
 887 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-win32-x64-gnu/-/rollup-win32-x64-gnu-4.62.3.tgz",
 888 |       "integrity": "sha512-vp7N084ew/odXn2gi/mzm9mUkQu9l6AiN6dt4IeUM2Uvm9o+cVmP+YkqbMOteLbiGgqBBlJZjIMYVCfOOIVbVQ==",
 889 |       "cpu": [
 890 |         "x64"
 891 |       ],
 892 |       "dev": true,
 893 |       "license": "MIT",
 894 |       "optional": true,
 895 |       "os": [
 896 |         "win32"
 897 |       ]
 898 |     },
 899 |     "node_modules/@rollup/rollup-win32-x64-msvc": {
 900 |       "version": "4.62.3",
 901 |       "resolved": "https://registry.npmmirror.com/@rollup/rollup-win32-x64-msvc/-/rollup-win32-x64-msvc-4.62.3.tgz",
 902 |       "integrity": "sha512-MOG/3gTOn4Fwf574RVOaY61I5o6P90legkFADiTyn1hyjNydT+cerU2rLUwPdZkKKyJ+iT+K9p7WXK4LM1Ka6g==",
 903 |       "cpu": [
 904 |         "x64"
 905 |       ],
 906 |       "dev": true,
 907 |       "license": "MIT",
 908 |       "optional": true,
 909 |       "os": [
 910 |         "win32"
 911 |       ]
 912 |     },
 913 |     "node_modules/@types/estree": {
 914 |       "version": "1.0.9",
 915 |       "resolved": "https://registry.npmmirror.com/@types/estree/-/estree-1.0.9.tgz",
 916 |       "integrity": "sha512-GhdPgy1el4/ImP05X05Uw4cw2/M93BCUmnEvWZNStlCzEKME4Fkk+YpoA5OiHNQmoS7Cafb8Xa3Pya8m1Qrzeg==",
 917 |       "dev": true,
 918 |       "license": "MIT"
 919 |     },
 920 |     "node_modules/@types/lodash": {
 921 |       "version": "4.17.24",
 922 |       "resolved": "https://registry.npmmirror.com/@types/lodash/-/lodash-4.17.24.tgz",
 923 |       "integrity": "sha512-gIW7lQLZbue7lRSWEFql49QJJWThrTFFeIMJdp3eH4tKoxm1OvEPg02rm4wCCSHS0cL3/Fizimb35b7k8atwsQ==",
 924 |       "license": "MIT"
 925 |     },
 926 |     "node_modules/@types/lodash-es": {
 927 |       "version": "4.17.12",
 928 |       "resolved": "https://registry.npmmirror.com/@types/lodash-es/-/lodash-es-4.17.12.tgz",
 929 |       "integrity": "sha512-0NgftHUcV4v34VhXm8QBSftKVXtbkBG3ViCjs6+eJ5a6y6Mi/jiFGPc1sC7QK+9BFhWrURE3EOggmWaSxL9OzQ==",
 930 |       "license": "MIT",
 931 |       "dependencies": {
 932 |         "@types/lodash": "*"
 933 |       }
 934 |     },
 935 |     "node_modules/@types/web-bluetooth": {
 936 |       "version": "0.0.21",
 937 |       "resolved": "https://registry.npmmirror.com/@types/web-bluetooth/-/web-bluetooth-0.0.21.tgz",
 938 |       "integrity": "sha512-oIQLCGWtcFZy2JW77j9k8nHzAOpqMHLQejDA48XXMWH6tjCQHz5RCFz1bzsmROyL6PUm+LLnUiI4BCn221inxA==",
 939 |       "license": "MIT"
 940 |     },
 941 |     "node_modules/@vitejs/plugin-vue": {
 942 |       "version": "5.2.4",
 943 |       "resolved": "https://registry.npmmirror.com/@vitejs/plugin-vue/-/plugin-vue-5.2.4.tgz",
 944 |       "integrity": "sha512-7Yx/SXSOcQq5HiiV3orevHUFn+pmMB4cgbEkDYgnkUWb0WfeQ/wa2yFv6D5ICiCQOVpjA7vYDXrC7AGO8yjDHA==",
 945 |       "dev": true,
 946 |       "license": "MIT",
 947 |       "engines": {
 948 |         "node": "^18.0.0 || >=20.0.0"
 949 |       },
 950 |       "peerDependencies": {
 951 |         "vite": "^5.0.0 || ^6.0.0",
 952 |         "vue": "^3.2.25"
 953 |       }
 954 |     },
 955 |     "node_modules/@vue/compiler-core": {
 956 |       "version": "3.5.40",
 957 |       "resolved": "https://registry.npmmirror.com/@vue/compiler-core/-/compiler-core-3.5.40.tgz",
 958 |       "integrity": "sha512-39E8IgOhTbVDnoJFMKc2DvYnypcZwUqgUhQkccva/0m6FUwtIKSGV7n1hpVmYcFaoRAwf9pBcwnKlCEsN63ZEQ==",
 959 |       "license": "MIT",
 960 |       "dependencies": {
 961 |         "@babel/parser": "^7.29.7",
 962 |         "@vue/shared": "3.5.40",
 963 |         "entities": "^7.0.1",
 964 |         "estree-walker": "^2.0.2",
 965 |         "source-map-js": "^1.2.1"
 966 |       }
 967 |     },
 968 |     "node_modules/@vue/compiler-dom": {
 969 |       "version": "3.5.40",
 970 |       "resolved": "https://registry.npmmirror.com/@vue/compiler-dom/-/compiler-dom-3.5.40.tgz",
 971 |       "integrity": "sha512-pwkx4vqlqOspFstrcmzwkKLePVMD3PT65imRzLhanU2V1Fj4K13g6OXjanOyzw3aTAuRk84BOmY8f3rEHqPaVA==",
 972 |       "license": "MIT",
 973 |       "dependencies": {
 974 |         "@vue/compiler-core": "3.5.40",
 975 |         "@vue/shared": "3.5.40"
 976 |       }
 977 |     },
 978 |     "node_modules/@vue/compiler-sfc": {
 979 |       "version": "3.5.40",
 980 |       "resolved": "https://registry.npmmirror.com/@vue/compiler-sfc/-/compiler-sfc-3.5.40.tgz",
 981 |       "integrity": "sha512-gIf497P4kpuALcvs5n3AEg1Vdn0pSY4XbjASIfHNYF1/MP3T2Mf2STERTubysBxCRxzJGJYtF/O7vwJrxFB3Vw==",
 982 |       "license": "MIT",
 983 |       "dependencies": {
 984 |         "@babel/parser": "^7.29.7",
 985 |         "@vue/compiler-core": "3.5.40",
 986 |         "@vue/compiler-dom": "3.5.40",
 987 |         "@vue/compiler-ssr": "3.5.40",
 988 |         "@vue/shared": "3.5.40",
 989 |         "estree-walker": "^2.0.2",
 990 |         "magic-string": "^0.30.21",
 991 |         "postcss": "^8.5.19",
 992 |         "source-map-js": "^1.2.1"
 993 |       }
 994 |     },
 995 |     "node_modules/@vue/compiler-ssr": {
 996 |       "version": "3.5.40",
 997 |       "resolved": "https://registry.npmmirror.com/@vue/compiler-ssr/-/compiler-ssr-3.5.40.tgz",
 998 |       "integrity": "sha512-rrE5xiXG663+vHCHa3J9p2z5OcBRjXmoqenprJxAFQxg5pSshzeBiCE6pu46axapRJ2Adk0YDA2BRZVjiHXnhg==",
 999 |       "license": "MIT",
1000 |       "dependencies": {
1001 |         "@vue/compiler-dom": "3.5.40",
1002 |         "@vue/shared": "3.5.40"
1003 |       }
1004 |     },
1005 |     "node_modules/@vue/devtools-api": {
1006 |       "version": "8.2.1",
1007 |       "resolved": "https://registry.npmmirror.com/@vue/devtools-api/-/devtools-api-8.2.1.tgz",
1008 |       "integrity": "sha512-6u4vXBlIBAC1wMplIZgpyPn7uh/s4Bf6F5bMzvLv+EdJ0aHs/+4B7Ygv864EStQSjRbsRzTko/kUG1A1IejQ3A==",
1009 |       "license": "MIT",
1010 |       "dependencies": {
1011 |         "@vue/devtools-kit": "^8.2.1"
1012 |       }
1013 |     },
1014 |     "node_modules/@vue/devtools-kit": {
1015 |       "version": "8.2.1",
1016 |       "resolved": "https://registry.npmmirror.com/@vue/devtools-kit/-/devtools-kit-8.2.1.tgz",
1017 |       "integrity": "sha512-FIGIuq3AWReEpbAHY/cRGeHDfI0qOb8OCQ3YjbEAX04uaxIDbGc9rhkbVcG7rnfHPXE3RsU5KrWOu9V/okd8AQ==",
1018 |       "license": "MIT",
1019 |       "dependencies": {
1020 |         "@vue/devtools-shared": "^8.2.1",
1021 |         "birpc": "^2.6.1",
1022 |         "hookable": "^5.5.3",
1023 |         "perfect-debounce": "^2.0.0"
1024 |       }
1025 |     },
1026 |     "node_modules/@vue/devtools-shared": {
1027 |       "version": "8.2.1",
1028 |       "resolved": "https://registry.npmmirror.com/@vue/devtools-shared/-/devtools-shared-8.2.1.tgz",
1029 |       "integrity": "sha512-Fkac7lUdGReh6pVOi3AYPRGe82LQqRmAfThW7RRligOAP0ZA/Z1z9XLHDM9dv34pV2HRc79DK8uKPeG2fLnA/g==",
1030 |       "license": "MIT"
1031 |     },
1032 |     "node_modules/@vue/reactivity": {
1033 |       "version": "3.5.40",
1034 |       "resolved": "https://registry.npmmirror.com/@vue/reactivity/-/reactivity-3.5.40.tgz",
1035 |       "integrity": "sha512-B7ot9UlUZOi1zbq61/LvE88ZLTV8IlajTdiZTAEiDQgrnIMIZoPr9kGw0Zw46ObW62O9+H/Be3kMbfb7kYPQZA==",
1036 |       "license": "MIT",
1037 |       "dependencies": {
1038 |         "@vue/shared": "3.5.40"
1039 |       }
1040 |     },
1041 |     "node_modules/@vue/runtime-core": {
1042 |       "version": "3.5.40",
1043 |       "resolved": "https://registry.npmmirror.com/@vue/runtime-core/-/runtime-core-3.5.40.tgz",
1044 |       "integrity": "sha512-KAZLweuZ6uUJPK1PMSQPgBU5gCjgrrfjUhSglmU9NhH+Zjepa8cnwSydPWDWHDwOgY4g3VcZ+PljbiHlURNCbw==",
1045 |       "license": "MIT",
1046 |       "dependencies": {
1047 |         "@vue/reactivity": "3.5.40",
1048 |         "@vue/shared": "3.5.40"
1049 |       }
1050 |     },
1051 |     "node_modules/@vue/runtime-dom": {
1052 |       "version": "3.5.40",
1053 |       "resolved": "https://registry.npmmirror.com/@vue/runtime-dom/-/runtime-dom-3.5.40.tgz",
1054 |       "integrity": "sha512-ZfrX8ssZQds900L9pr8AuK05ddnMsR4MPMZr8cPN9GoqoPWcXLhjvvbIA2SMv+7a97sJ1vv9pj/zxK0Cq/eEFQ==",
1055 |       "license": "MIT",
1056 |       "dependencies": {
1057 |         "@vue/reactivity": "3.5.40",
1058 |         "@vue/runtime-core": "3.5.40",
1059 |         "@vue/shared": "3.5.40",
1060 |         "csstype": "^3.2.3"
1061 |       }
1062 |     },
1063 |     "node_modules/@vue/server-renderer": {
1064 |       "version": "3.5.40",
1065 |       "resolved": "https://registry.npmmirror.com/@vue/server-renderer/-/server-renderer-3.5.40.tgz",
1066 |       "integrity": "sha512-XNJym9WpevhTVt1HuwOrCRJ5Q+9z4BjTMrDtjTrvx74SmUll8spNTw6whWJa9mEkO4PKn5TihI/bm/8ds2QVJw==",
1067 |       "license": "MIT",
1068 |       "dependencies": {
1069 |         "@vue/compiler-ssr": "3.5.40",
1070 |         "@vue/runtime-dom": "3.5.40",
1071 |         "@vue/shared": "3.5.40"
1072 |       }
1073 |     },
1074 |     "node_modules/@vue/shared": {
1075 |       "version": "3.5.40",
1076 |       "resolved": "https://registry.npmmirror.com/@vue/shared/-/shared-3.5.40.tgz",
1077 |       "integrity": "sha512-WxnBtruIqOoV3rA4jeKDWzrYI5h7Cp4+pjwDi8kWGHz+IslhiN+wguLVVhtv2l8VoU02rzDCVfDjgCl1lNpZVg==",
1078 |       "license": "MIT"
1079 |     },
1080 |     "node_modules/@vueuse/core": {
1081 |       "version": "14.3.0",
1082 |       "resolved": "https://registry.npmmirror.com/@vueuse/core/-/core-14.3.0.tgz",
1083 |       "integrity": "sha512-aHfz47g0ZhMtTVHmIzMVpJy8ePhhOy68GY5bv110+5DVtZ+W7BsOx+m61UNQqfrWyPztIHIanWa3E2tib3NFIw==",
1084 |       "license": "MIT",
1085 |       "dependencies": {
1086 |         "@types/web-bluetooth": "^0.0.21",
1087 |         "@vueuse/metadata": "14.3.0",
1088 |         "@vueuse/shared": "14.3.0"
1089 |       },
1090 |       "funding": {
1091 |         "url": "https://github.com/sponsors/antfu"
1092 |       },
1093 |       "peerDependencies": {
1094 |         "vue": "^3.5.0"
1095 |       }
1096 |     },
1097 |     "node_modules/@vueuse/metadata": {
1098 |       "version": "14.3.0",
1099 |       "resolved": "https://registry.npmmirror.com/@vueuse/metadata/-/metadata-14.3.0.tgz",
1100 |       "integrity": "sha512-BwxmbAzwAVF50+MW57GXOUEV61nFBGnlBvrTqj49PqWJu3uw7hdu72ztXeZ33RdZtDY6kO+bfCAE1PCn88Tktw==",
1101 |       "license": "MIT",
1102 |       "funding": {
1103 |         "url": "https://github.com/sponsors/antfu"
1104 |       }
1105 |     },
1106 |     "node_modules/@vueuse/shared": {
1107 |       "version": "14.3.0",
1108 |       "resolved": "https://registry.npmmirror.com/@vueuse/shared/-/shared-14.3.0.tgz",
1109 |       "integrity": "sha512-bZpge9eSXwa4ToSiqJ7j6KRwhAsneMFoSz3LMWKQDkqimm3D/tbFlrklrs/IOqC8tEcYmXQZJ6N0UrjhBirVCg==",
1110 |       "license": "MIT",
1111 |       "funding": {
1112 |         "url": "https://github.com/sponsors/antfu"
1113 |       },
1114 |       "peerDependencies": {
1115 |         "vue": "^3.5.0"
1116 |       }
1117 |     },
1118 |     "node_modules/agent-base": {
1119 |       "version": "6.0.2",
1120 |       "resolved": "https://registry.npmmirror.com/agent-base/-/agent-base-6.0.2.tgz",
1121 |       "integrity": "sha512-RZNwNclF7+MS/8bDg70amg32dyeZGZxiDuQmZxKLAlQjr3jGyLx+4Kkk58UO7D2QdgFIQCovuSuZESne6RG6XQ==",
1122 |       "license": "MIT",
1123 |       "dependencies": {
1124 |         "debug": "4"
1125 |       },
1126 |       "engines": {
1127 |         "node": ">= 6.0.0"
1128 |       }
1129 |     },
1130 |     "node_modules/async-validator": {
1131 |       "version": "4.2.5",
1132 |       "resolved": "https://registry.npmmirror.com/async-validator/-/async-validator-4.2.5.tgz",
1133 |       "integrity": "sha512-7HhHjtERjqlNbZtqNqy2rckN/SpOOlmDliet+lP7k+eKZEjPk3DgyeU9lIXLdeLz0uBbbVp+9Qdow9wJWgwwfg==",
1134 |       "license": "MIT"
1135 |     },
1136 |     "node_modules/asynckit": {
1137 |       "version": "0.4.0",
1138 |       "resolved": "https://registry.npmmirror.com/asynckit/-/asynckit-0.4.0.tgz",
1139 |       "integrity": "sha512-Oei9OH4tRh0YqU3GxhX79dM/mwVgvbZJaSNaRk+bshkj0S5cfHcgYakreBjrHwatXKbz+IoIdYLxrKim2MjW0Q==",
1140 |       "license": "MIT"
1141 |     },
1142 |     "node_modules/axios": {
1143 |       "version": "1.18.1",
1144 |       "resolved": "https://registry.npmmirror.com/axios/-/axios-1.18.1.tgz",
1145 |       "integrity": "sha512-3nTvFlvpn9Zu/RkHUqtc7/+al4UpRW5az71ap5zccp6e8RAYEzhMTecX8Dz1wWDYrPpUoB1HAQEGEAEvUr7S9g==",
1146 |       "license": "MIT",
1147 |       "dependencies": {
1148 |         "follow-redirects": "^1.16.0",
1149 |         "form-data": "^4.0.5",
1150 |         "https-proxy-agent": "^5.0.1",
1151 |         "proxy-from-env": "^2.1.0"
1152 |       }
1153 |     },
1154 |     "node_modules/birpc": {
1155 |       "version": "2.9.0",
1156 |       "resolved": "https://registry.npmmirror.com/birpc/-/birpc-2.9.0.tgz",
1157 |       "integrity": "sha512-KrayHS5pBi69Xi9JmvoqrIgYGDkD6mcSe/i6YKi3w5kekCLzrX4+nawcXqrj2tIp50Kw/mT/s3p+GVK0A0sKxw==",
1158 |       "license": "MIT",
1159 |       "funding": {
1160 |         "url": "https://github.com/sponsors/antfu"
1161 |       }
1162 |     },
1163 |     "node_modules/call-bind-apply-helpers": {
1164 |       "version": "1.0.2",
1165 |       "resolved": "https://registry.npmmirror.com/call-bind-apply-helpers/-/call-bind-apply-helpers-1.0.2.tgz",
1166 |       "integrity": "sha512-Sp1ablJ0ivDkSzjcaJdxEunN5/XvksFJ2sMBFfq6x0ryhQV/2b/KwFe21cMpmHtPOSij8K99/wSfoEuTObmuMQ==",
1167 |       "license": "MIT",
1168 |       "dependencies": {
1169 |         "es-errors": "^1.3.0",
1170 |         "function-bind": "^1.1.2"
1171 |       },
1172 |       "engines": {
1173 |         "node": ">= 0.4"
1174 |       }
1175 |     },
1176 |     "node_modules/combined-stream": {
1177 |       "version": "1.0.8",
1178 |       "resolved": "https://registry.npmmirror.com/combined-stream/-/combined-stream-1.0.8.tgz",
1179 |       "integrity": "sha512-FQN4MRfuJeHf7cBbBMJFXhKSDq+2kAArBlmRBvcvFE5BB1HZKXtSFASDhdlz9zOYwxh8lDdnvmMOe/+5cdoEdg==",
1180 |       "license": "MIT",
1181 |       "dependencies": {
1182 |         "delayed-stream": "~1.0.0"
1183 |       },
1184 |       "engines": {
1185 |         "node": ">= 0.8"
1186 |       }
1187 |     },
1188 |     "node_modules/csstype": {
1189 |       "version": "3.2.3",
1190 |       "resolved": "https://registry.npmmirror.com/csstype/-/csstype-3.2.3.tgz",
1191 |       "integrity": "sha512-z1HGKcYy2xA8AGQfwrn0PAy+PB7X/GSj3UVJW9qKyn43xWa+gl5nXmU4qqLMRzWVLFC8KusUX8T/0kCiOYpAIQ==",
1192 |       "license": "MIT"
1193 |     },
1194 |     "node_modules/dayjs": {
1195 |       "version": "1.11.21",
1196 |       "resolved": "https://registry.npmmirror.com/dayjs/-/dayjs-1.11.21.tgz",
1197 |       "integrity": "sha512-98IT+HOahAisibz/yjKbzuOBwYcjJ7BCLPzARyHiyEBmRz4fatF+KPJszEHXsGYjUG234aH/cOjW1wwTbKUZlA==",
1198 |       "license": "MIT"
1199 |     },
1200 |     "node_modules/debug": {
1201 |       "version": "4.4.3",
1202 |       "resolved": "https://registry.npmmirror.com/debug/-/debug-4.4.3.tgz",
1203 |       "integrity": "sha512-RGwwWnwQvkVfavKVt22FGLw+xYSdzARwm0ru6DhTVA3umU5hZc28V3kO4stgYryrTlLpuvgI9GiijltAjNbcqA==",
1204 |       "license": "MIT",
1205 |       "dependencies": {
1206 |         "ms": "^2.1.3"
1207 |       },
1208 |       "engines": {
1209 |         "node": ">=6.0"
1210 |       },
1211 |       "peerDependenciesMeta": {
1212 |         "supports-color": {
1213 |           "optional": true
1214 |         }
1215 |       }
1216 |     },
1217 |     "node_modules/delayed-stream": {
1218 |       "version": "1.0.0",
1219 |       "resolved": "https://registry.npmmirror.com/delayed-stream/-/delayed-stream-1.0.0.tgz",
1220 |       "integrity": "sha512-ZySD7Nf91aLB0RxL4KGrKHBXl7Eds1DAmEdcoVawXnLD7SDhpNgtuII2aAkg7a7QS41jxPSZ17p4VdGnMHk3MQ==",
1221 |       "license": "MIT",
1222 |       "engines": {
1223 |         "node": ">=0.4.0"
1224 |       }
1225 |     },
1226 |     "node_modules/dunder-proto": {
1227 |       "version": "1.0.1",
1228 |       "resolved": "https://registry.npmmirror.com/dunder-proto/-/dunder-proto-1.0.1.tgz",
1229 |       "integrity": "sha512-KIN/nDJBQRcXw0MLVhZE9iQHmG68qAVIBg9CqmUYjmQIhgij9U5MFvrqkUL5FbtyyzZuOeOt0zdeRe4UY7ct+A==",
1230 |       "license": "MIT",
1231 |       "dependencies": {
1232 |         "call-bind-apply-helpers": "^1.0.1",
1233 |         "es-errors": "^1.3.0",
1234 |         "gopd": "^1.2.0"
1235 |       },
1236 |       "engines": {
1237 |         "node": ">= 0.4"
1238 |       }
1239 |     },
1240 |     "node_modules/element-plus": {
1241 |       "version": "2.14.3",
1242 |       "resolved": "https://registry.npmmirror.com/element-plus/-/element-plus-2.14.3.tgz",
1243 |       "integrity": "sha512-pJcvxcpZjYruNzuJhAeVwnbYjfNgzBKnWHwSVEhwzM2/kcLI3brzmtIBxtPqd4hQWJfD1PRnjoc1WipLw2eBGg==",
1244 |       "license": "MIT",
1245 |       "dependencies": {
1246 |         "@ctrl/tinycolor": "^4.2.0",
1247 |         "@element-plus/icons-vue": "^2.3.2",
1248 |         "@floating-ui/dom": "^1.7.6",
1249 |         "@popperjs/core": "npm:@sxzz/popperjs-es@^2.11.8",
1250 |         "@types/lodash": "^4.17.24",
1251 |         "@types/lodash-es": "^4.17.12",
1252 |         "@vueuse/core": "14.3.0",
1253 |         "async-validator": "^4.2.5",
1254 |         "dayjs": "^1.11.20",
1255 |         "lodash": "^4.18.1",
1256 |         "lodash-es": "^4.18.1",
1257 |         "lodash-unified": "^1.0.3",
1258 |         "memoize-one": "^6.0.0",
1259 |         "normalize-wheel-es": "^1.2.0",
1260 |         "vue-component-type-helpers": "^3.3.5"
1261 |       },
1262 |       "peerDependencies": {
1263 |         "vue": "^3.3.7"
1264 |       }
1265 |     },
1266 |     "node_modules/entities": {
1267 |       "version": "7.0.1",
1268 |       "resolved": "https://registry.npmmirror.com/entities/-/entities-7.0.1.tgz",
1269 |       "integrity": "sha512-TWrgLOFUQTH994YUyl1yT4uyavY5nNB5muff+RtWaqNVCAK408b5ZnnbNAUEWLTCpum9w6arT70i1XdQ4UeOPA==",
1270 |       "license": "BSD-2-Clause",
1271 |       "engines": {
1272 |         "node": ">=0.12"
1273 |       },
1274 |       "funding": {
1275 |         "url": "https://github.com/fb55/entities?sponsor=1"
1276 |       }
1277 |     },
1278 |     "node_modules/es-define-property": {
1279 |       "version": "1.0.1",
1280 |       "resolved": "https://registry.npmmirror.com/es-define-property/-/es-define-property-1.0.1.tgz",
1281 |       "integrity": "sha512-e3nRfgfUZ4rNGL232gUgX06QNyyez04KdjFrF+LTRoOXmrOgFKDg4BCdsjW8EnT69eqdYGmRpJwiPVYNrCaW3g==",
1282 |       "license": "MIT",
1283 |       "engines": {
1284 |         "node": ">= 0.4"
1285 |       }
1286 |     },
1287 |     "node_modules/es-errors": {
1288 |       "version": "1.3.0",
1289 |       "resolved": "https://registry.npmmirror.com/es-errors/-/es-errors-1.3.0.tgz",
1290 |       "integrity": "sha512-Zf5H2Kxt2xjTvbJvP2ZWLEICxA6j+hAmMzIlypy4xcBg1vKVnx89Wy0GbS+kf5cwCVFFzdCFh2XSCFNULS6csw==",
1291 |       "license": "MIT",
1292 |       "engines": {
1293 |         "node": ">= 0.4"
1294 |       }
1295 |     },
1296 |     "node_modules/es-object-atoms": {
1297 |       "version": "1.1.2",
1298 |       "resolved": "https://registry.npmmirror.com/es-object-atoms/-/es-object-atoms-1.1.2.tgz",
1299 |       "integrity": "sha512-HWcBoN6NileqtSydK2FqHbS/LoDd2pqrnQHLyJzBj4kOp/ky2MWMN694xOfkK8/SnUsW2DH7EfyVlydKCsm1Zw==",
1300 |       "license": "MIT",
1301 |       "dependencies": {
1302 |         "es-errors": "^1.3.0"
1303 |       },
1304 |       "engines": {
1305 |         "node": ">= 0.4"
1306 |       }
1307 |     },
1308 |     "node_modules/es-set-tostringtag": {
1309 |       "version": "2.1.0",
1310 |       "resolved": "https://registry.npmmirror.com/es-set-tostringtag/-/es-set-tostringtag-2.1.0.tgz",
1311 |       "integrity": "sha512-j6vWzfrGVfyXxge+O0x5sh6cvxAog0a/4Rdd2K36zCMV5eJ+/+tOAngRO8cODMNWbVRdVlmGZQL2YS3yR8bIUA==",
1312 |       "license": "MIT",
1313 |       "dependencies": {
1314 |         "es-errors": "^1.3.0",
1315 |         "get-intrinsic": "^1.2.6",
1316 |         "has-tostringtag": "^1.0.2",
1317 |         "hasown": "^2.0.2"
1318 |       },
1319 |       "engines": {
1320 |         "node": ">= 0.4"
1321 |       }
1322 |     },
1323 |     "node_modules/esbuild": {
1324 |       "version": "0.21.5",
1325 |       "resolved": "https://registry.npmmirror.com/esbuild/-/esbuild-0.21.5.tgz",
1326 |       "integrity": "sha512-mg3OPMV4hXywwpoDxu3Qda5xCKQi+vCTZq8S9J/EpkhB2HzKXq4SNFZE3+NK93JYxc8VMSep+lOUSC/RVKaBqw==",
1327 |       "dev": true,
1328 |       "hasInstallScript": true,
1329 |       "license": "MIT",
1330 |       "bin": {
1331 |         "esbuild": "bin/esbuild"
1332 |       },
1333 |       "engines": {
1334 |         "node": ">=12"
1335 |       },
1336 |       "optionalDependencies": {
1337 |         "@esbuild/aix-ppc64": "0.21.5",
1338 |         "@esbuild/android-arm": "0.21.5",
1339 |         "@esbuild/android-arm64": "0.21.5",
1340 |         "@esbuild/android-x64": "0.21.5",
1341 |         "@esbuild/darwin-arm64": "0.21.5",
1342 |         "@esbuild/darwin-x64": "0.21.5",
1343 |         "@esbuild/freebsd-arm64": "0.21.5",
1344 |         "@esbuild/freebsd-x64": "0.21.5",
1345 |         "@esbuild/linux-arm": "0.21.5",
1346 |         "@esbuild/linux-arm64": "0.21.5",
1347 |         "@esbuild/linux-ia32": "0.21.5",
1348 |         "@esbuild/linux-loong64": "0.21.5",
1349 |         "@esbuild/linux-mips64el": "0.21.5",
1350 |         "@esbuild/linux-ppc64": "0.21.5",
1351 |         "@esbuild/linux-riscv64": "0.21.5",
1352 |         "@esbuild/linux-s390x": "0.21.5",
1353 |         "@esbuild/linux-x64": "0.21.5",
1354 |         "@esbuild/netbsd-x64": "0.21.5",
1355 |         "@esbuild/openbsd-x64": "0.21.5",
1356 |         "@esbuild/sunos-x64": "0.21.5",
1357 |         "@esbuild/win32-arm64": "0.21.5",
1358 |         "@esbuild/win32-ia32": "0.21.5",
1359 |         "@esbuild/win32-x64": "0.21.5"
1360 |       }
1361 |     },
1362 |     "node_modules/estree-walker": {
1363 |       "version": "2.0.2",
1364 |       "resolved": "https://registry.npmmirror.com/estree-walker/-/estree-walker-2.0.2.tgz",
1365 |       "integrity": "sha512-Rfkk/Mp/DL7JVje3u18FxFujQlTNR2q6QfMSMB7AvCBx91NGj/ba3kCfza0f6dVDbw7YlRf/nDrn7pQrCCyQ/w==",
1366 |       "license": "MIT"
1367 |     },
1368 |     "node_modules/follow-redirects": {
1369 |       "version": "1.16.0",
1370 |       "resolved": "https://registry.npmmirror.com/follow-redirects/-/follow-redirects-1.16.0.tgz",
1371 |       "integrity": "sha512-y5rN/uOsadFT/JfYwhxRS5R7Qce+g3zG97+JrtFZlC9klX/W5hD7iiLzScI4nZqUS7DNUdhPgw4xI8W2LuXlUw==",
1372 |       "funding": [
1373 |         {
1374 |           "type": "individual",
1375 |           "url": "https://github.com/sponsors/RubenVerborgh"
1376 |         }
1377 |       ],
1378 |       "license": "MIT",
1379 |       "engines": {
1380 |         "node": ">=4.0"
1381 |       },
1382 |       "peerDependenciesMeta": {
1383 |         "debug": {
1384 |           "optional": true
1385 |         }
1386 |       }
1387 |     },
1388 |     "node_modules/form-data": {
1389 |       "version": "4.0.6",
1390 |       "resolved": "https://registry.npmmirror.com/form-data/-/form-data-4.0.6.tgz",
1391 |       "integrity": "sha512-vKatAh4SlVfgbv+YtmhiRjhEMJsYpsG1Y2rMQtR+SVSbytsSD1YGzDIcrAJmdFec88u/+VoGmxnl+80gL1tRCQ==",
1392 |       "license": "MIT",
1393 |       "dependencies": {
1394 |         "asynckit": "^0.4.0",
1395 |         "combined-stream": "^1.0.8",
1396 |         "es-set-tostringtag": "^2.1.0",
1397 |         "hasown": "^2.0.4",
1398 |         "mime-types": "^2.1.35"
1399 |       },
1400 |       "engines": {
1401 |         "node": ">= 6"
1402 |       }
1403 |     },
1404 |     "node_modules/fsevents": {
1405 |       "version": "2.3.3",
1406 |       "resolved": "https://registry.npmmirror.com/fsevents/-/fsevents-2.3.3.tgz",
1407 |       "integrity": "sha512-5xoDfX+fL7faATnagmWPpbFtwh/R77WmMMqqHGS65C3vvB0YHrgF+B1YmZ3441tMj5n63k0212XNoJwzlhffQw==",
1408 |       "dev": true,
1409 |       "hasInstallScript": true,
1410 |       "license": "MIT",
1411 |       "optional": true,
1412 |       "os": [
1413 |         "darwin"
1414 |       ],
1415 |       "engines": {
1416 |         "node": "^8.16.0 || ^10.6.0 || >=11.0.0"
1417 |       }
1418 |     },
1419 |     "node_modules/function-bind": {
1420 |       "version": "1.1.2",
1421 |       "resolved": "https://registry.npmmirror.com/function-bind/-/function-bind-1.1.2.tgz",
1422 |       "integrity": "sha512-7XHNxH7qX9xG5mIwxkhumTox/MIRNcOgDrxWsMt2pAr23WHp6MrRlN7FBSFpCpr+oVO0F744iUgR82nJMfG2SA==",
1423 |       "license": "MIT",
1424 |       "funding": {
1425 |         "url": "https://github.com/sponsors/ljharb"
1426 |       }
1427 |     },
1428 |     "node_modules/get-intrinsic": {
1429 |       "version": "1.3.0",
1430 |       "resolved": "https://registry.npmmirror.com/get-intrinsic/-/get-intrinsic-1.3.0.tgz",
1431 |       "integrity": "sha512-9fSjSaos/fRIVIp+xSJlE6lfwhES7LNtKaCBIamHsjr2na1BiABJPo0mOjjz8GJDURarmCPGqaiVg5mfjb98CQ==",
1432 |       "license": "MIT",
1433 |       "dependencies": {
1434 |         "call-bind-apply-helpers": "^1.0.2",
1435 |         "es-define-property": "^1.0.1",
1436 |         "es-errors": "^1.3.0",
1437 |         "es-object-atoms": "^1.1.1",
1438 |         "function-bind": "^1.1.2",
1439 |         "get-proto": "^1.0.1",
1440 |         "gopd": "^1.2.0",
1441 |         "has-symbols": "^1.1.0",
1442 |         "hasown": "^2.0.2",
1443 |         "math-intrinsics": "^1.1.0"
1444 |       },
1445 |       "engines": {
1446 |         "node": ">= 0.4"
1447 |       },
1448 |       "funding": {
1449 |         "url": "https://github.com/sponsors/ljharb"
1450 |       }
1451 |     },
1452 |     "node_modules/get-proto": {
1453 |       "version": "1.0.1",
1454 |       "resolved": "https://registry.npmmirror.com/get-proto/-/get-proto-1.0.1.tgz",
1455 |       "integrity": "sha512-sTSfBjoXBp89JvIKIefqw7U2CCebsc74kiY6awiGogKtoSGbgjYE/G/+l9sF3MWFPNc9IcoOC4ODfKHfxFmp0g==",
1456 |       "license": "MIT",
1457 |       "dependencies": {
1458 |         "dunder-proto": "^1.0.1",
1459 |         "es-object-atoms": "^1.0.0"
1460 |       },
1461 |       "engines": {
1462 |         "node": ">= 0.4"
1463 |       }
1464 |     },
1465 |     "node_modules/gopd": {
1466 |       "version": "1.2.0",
1467 |       "resolved": "https://registry.npmmirror.com/gopd/-/gopd-1.2.0.tgz",
1468 |       "integrity": "sha512-ZUKRh6/kUFoAiTAtTYPZJ3hw9wNxx+BIBOijnlG9PnrJsCcSjs1wyyD6vJpaYtgnzDrKYRSqf3OO6Rfa93xsRg==",
1469 |       "license": "MIT",
1470 |       "engines": {
1471 |         "node": ">= 0.4"
1472 |       },
1473 |       "funding": {
1474 |         "url": "https://github.com/sponsors/ljharb"
1475 |       }
1476 |     },
1477 |     "node_modules/has-symbols": {
1478 |       "version": "1.1.0",
1479 |       "resolved": "https://registry.npmmirror.com/has-symbols/-/has-symbols-1.1.0.tgz",
1480 |       "integrity": "sha512-1cDNdwJ2Jaohmb3sg4OmKaMBwuC48sYni5HUw2DvsC8LjGTLK9h+eb1X6RyuOHe4hT0ULCW68iomhjUoKUqlPQ==",
1481 |       "license": "MIT",
1482 |       "engines": {
1483 |         "node": ">= 0.4"
1484 |       },
1485 |       "funding": {
1486 |         "url": "https://github.com/sponsors/ljharb"
1487 |       }
1488 |     },
1489 |     "node_modules/has-tostringtag": {
1490 |       "version": "1.0.2",
1491 |       "resolved": "https://registry.npmmirror.com/has-tostringtag/-/has-tostringtag-1.0.2.tgz",
1492 |       "integrity": "sha512-NqADB8VjPFLM2V0VvHUewwwsw0ZWBaIdgo+ieHtK3hasLz4qeCRjYcqfB6AQrBggRKppKF8L52/VqdVsO47Dlw==",
1493 |       "license": "MIT",
1494 |       "dependencies": {
1495 |         "has-symbols": "^1.0.3"
1496 |       },
1497 |       "engines": {
1498 |         "node": ">= 0.4"
1499 |       },
1500 |       "funding": {
1501 |         "url": "https://github.com/sponsors/ljharb"
1502 |       }
1503 |     },
1504 |     "node_modules/hasown": {
1505 |       "version": "2.0.4",
1506 |       "resolved": "https://registry.npmmirror.com/hasown/-/hasown-2.0.4.tgz",
1507 |       "integrity": "sha512-T2UbfbBEF32wiepXIsMlTW9+dDYC6wMh/t/vYA4tuOMKqWz/n3vr1NFSxQiyP+zk2mXsoMA/i/7qV6LKut1t1A==",
1508 |       "license": "MIT",
1509 |       "dependencies": {
1510 |         "function-bind": "^1.1.2"
1511 |       },
1512 |       "engines": {
1513 |         "node": ">= 0.4"
1514 |       }
1515 |     },
1516 |     "node_modules/heap": {
1517 |       "version": "0.2.5",
1518 |       "resolved": "https://registry.npmmirror.com/heap/-/heap-0.2.5.tgz",
1519 |       "integrity": "sha512-G7HLD+WKcrOyJP5VQwYZNC3Z6FcQ7YYjEFiFoIj8PfEr73mu421o8B1N5DKUcc8K37EsJ2XXWA8DtrDz/2dReg=="
1520 |     },
1521 |     "node_modules/hookable": {
1522 |       "version": "5.5.3",
1523 |       "resolved": "https://registry.npmmirror.com/hookable/-/hookable-5.5.3.tgz",
1524 |       "integrity": "sha512-Yc+BQe8SvoXH1643Qez1zqLRmbA5rCL+sSmk6TVos0LWVfNIB7PGncdlId77WzLGSIB5KaWgTaNTs2lNVEI6VQ==",
1525 |       "license": "MIT"
1526 |     },
1527 |     "node_modules/https-proxy-agent": {
1528 |       "version": "5.0.1",
1529 |       "resolved": "https://registry.npmmirror.com/https-proxy-agent/-/https-proxy-agent-5.0.1.tgz",
1530 |       "integrity": "sha512-dFcAjpTQFgoLMzC2VwU+C/CbS7uRL0lWmxDITmqm7C+7F0Odmj6s9l6alZc6AELXhrnggM2CeWSXHGOdX2YtwA==",
1531 |       "license": "MIT",
1532 |       "dependencies": {
1533 |         "agent-base": "6",
1534 |         "debug": "4"
1535 |       },
1536 |       "engines": {
1537 |         "node": ">= 6"
1538 |       }
1539 |     },
1540 |     "node_modules/lodash": {
1541 |       "version": "4.18.1",
1542 |       "resolved": "https://registry.npmmirror.com/lodash/-/lodash-4.18.1.tgz",
1543 |       "integrity": "sha512-dMInicTPVE8d1e5otfwmmjlxkZoUpiVLwyeTdUsi/Caj/gfzzblBcCE5sRHV/AsjuCmxWrte2TNGSYuCeCq+0Q==",
1544 |       "license": "MIT"
1545 |     },
1546 |     "node_modules/lodash-es": {
1547 |       "version": "4.18.1",
1548 |       "resolved": "https://registry.npmmirror.com/lodash-es/-/lodash-es-4.18.1.tgz",
1549 |       "integrity": "sha512-J8xewKD/Gk22OZbhpOVSwcs60zhd95ESDwezOFuA3/099925PdHJ7OFHNTGtajL3AlZkykD32HykiMo+BIBI8A==",
1550 |       "license": "MIT"
1551 |     },
1552 |     "node_modules/lodash-unified": {
1553 |       "version": "1.0.3",
1554 |       "resolved": "https://registry.npmmirror.com/lodash-unified/-/lodash-unified-1.0.3.tgz",
1555 |       "integrity": "sha512-WK9qSozxXOD7ZJQlpSqOT+om2ZfcT4yO+03FuzAHD0wF6S0l0090LRPDx3vhTTLZ8cFKpBn+IOcVXK6qOcIlfQ==",
1556 |       "license": "MIT",
1557 |       "peerDependencies": {
1558 |         "@types/lodash-es": "*",
1559 |         "lodash": "*",
1560 |         "lodash-es": "*"
1561 |       }
1562 |     },
1563 |     "node_modules/lucide-vue-next": {
1564 |       "version": "0.577.0",
1565 |       "resolved": "https://registry.npmmirror.com/lucide-vue-next/-/lucide-vue-next-0.577.0.tgz",
1566 |       "integrity": "sha512-py05bAfv9SHVJqscbiOnjcnLlEmOffA58a+7XhZuFxrs6txe1E8VoR1ngWGTYO+9aVKABAz8l3ee3PqiQN9QPA==",
1567 |       "license": "ISC",
1568 |       "peerDependencies": {
1569 |         "vue": ">=3.0.1"
1570 |       }
1571 |     },
1572 |     "node_modules/magic-string": {
1573 |       "version": "0.30.21",
1574 |       "resolved": "https://registry.npmmirror.com/magic-string/-/magic-string-0.30.21.tgz",
1575 |       "integrity": "sha512-vd2F4YUyEXKGcLHoq+TEyCjxueSeHnFxyyjNp80yg0XV4vUhnDer/lvvlqM/arB5bXQN5K2/3oinyCRyx8T2CQ==",
1576 |       "license": "MIT",
1577 |       "dependencies": {
1578 |         "@jridgewell/sourcemap-codec": "^1.5.5"
1579 |       }
1580 |     },
1581 |     "node_modules/math-intrinsics": {
1582 |       "version": "1.1.0",
1583 |       "resolved": "https://registry.npmmirror.com/math-intrinsics/-/math-intrinsics-1.1.0.tgz",
1584 |       "integrity": "sha512-/IXtbwEk5HTPyEwyKX6hGkYXxM9nbj64B+ilVJnC/R6B0pH5G4V3b0pVbL7DBj4tkhBAppbQUlf6F6Xl9LHu1g==",
1585 |       "license": "MIT",
1586 |       "engines": {
1587 |         "node": ">= 0.4"
1588 |       }
1589 |     },
1590 |     "node_modules/memoize-one": {
1591 |       "version": "6.0.0",
1592 |       "resolved": "https://registry.npmmirror.com/memoize-one/-/memoize-one-6.0.0.tgz",
1593 |       "integrity": "sha512-rkpe71W0N0c0Xz6QD0eJETuWAJGnJ9afsl1srmwPrI+yBCkge5EycXXbYRyvL29zZVUWQCY7InPRCv3GDXuZNw==",
1594 |       "license": "MIT"
1595 |     },
1596 |     "node_modules/mime-db": {
1597 |       "version": "1.52.0",
1598 |       "resolved": "https://registry.npmmirror.com/mime-db/-/mime-db-1.52.0.tgz",
1599 |       "integrity": "sha512-sPU4uV7dYlvtWJxwwxHD0PuihVNiE7TyAbQ5SWxDCB9mUYvOgroQOwYQQOKPJ8CIbE+1ETVlOoK1UC2nU3gYvg==",
1600 |       "license": "MIT",
1601 |       "engines": {
1602 |         "node": ">= 0.6"
1603 |       }
1604 |     },
1605 |     "node_modules/mime-types": {
1606 |       "version": "2.1.35",
1607 |       "resolved": "https://registry.npmmirror.com/mime-types/-/mime-types-2.1.35.tgz",
1608 |       "integrity": "sha512-ZDY+bPm5zTTF+YpCrAU9nK0UgICYPT0QtT1NZWFv4s++TNkcgVaT0g6+4R2uI4MjQjzysHB1zxuWL50hzaeXiw==",
1609 |       "license": "MIT",
1610 |       "dependencies": {
1611 |         "mime-db": "1.52.0"
1612 |       },
1613 |       "engines": {
1614 |         "node": ">= 0.6"
1615 |       }
1616 |     },
1617 |     "node_modules/ms": {
1618 |       "version": "2.1.3",
1619 |       "resolved": "https://registry.npmmirror.com/ms/-/ms-2.1.3.tgz",
1620 |       "integrity": "sha512-6FlzubTLZG3J2a/NVCAleEhjzq5oxgHyaCU9yYXvcLsvoVaHJq/s5xXI6/XXP6tz7R9xAOtHnSO/tXtF3WRTlA==",
1621 |       "license": "MIT"
1622 |     },
1623 |     "node_modules/nanoid": {
1624 |       "version": "3.3.16",
1625 |       "resolved": "https://registry.npmmirror.com/nanoid/-/nanoid-3.3.16.tgz",
1626 |       "integrity": "sha512-bzlKTyNJ7+LdGIIwy8ijFpIqEQIvafahV7eYykJ8Cvh42EdJeODoJ6gUJXpQJvej1BddH8OqTXZNE/KfbWAu8Q==",
1627 |       "funding": [
1628 |         {
1629 |           "type": "github",
1630 |           "url": "https://github.com/sponsors/ai"
1631 |         }
1632 |       ],
1633 |       "license": "MIT",
1634 |       "bin": {
1635 |         "nanoid": "bin/nanoid.cjs"
1636 |       },
1637 |       "engines": {
1638 |         "node": "^10 || ^12 || ^13.7 || ^14 || >=15.0.1"
1639 |       }
1640 |     },
1641 |     "node_modules/normalize-wheel-es": {
1642 |       "version": "1.2.0",
1643 |       "resolved": "https://registry.npmmirror.com/normalize-wheel-es/-/normalize-wheel-es-1.2.0.tgz",
1644 |       "integrity": "sha512-Wj7+EJQ8mSuXr2iWfnujrimU35R2W4FAErEyTmJoJ7ucwTn2hOUSsRehMb5RSYkxXGTM7Y9QpvPmp++w5ftoJw==",
1645 |       "license": "BSD-3-Clause"
1646 |     },
1647 |     "node_modules/nostics": {
1648 |       "version": "1.2.0",
1649 |       "resolved": "https://registry.npmmirror.com/nostics/-/nostics-1.2.0.tgz",
1650 |       "integrity": "sha512-FGqEfhQjrvo1lL8KFifdTQiNwwQHJxC1jtYE1Rc54qF/jxONUNL+kC9gS1krX8Q65PgrQ5fCqH/I4NhWBvdSqg==",
1651 |       "license": "MIT"
1652 |     },
1653 |     "node_modules/pathfinding": {
1654 |       "version": "0.4.18",
1655 |       "resolved": "https://registry.npmmirror.com/pathfinding/-/pathfinding-0.4.18.tgz",
1656 |       "integrity": "sha512-R0TGEQ9GRcFCDvAWlJAWC+KGJ9SLbW4c0nuZRcioVlXVTlw+F5RvXQ8SQgSqI9KXWC1ew95vgmIiyaWTlCe9Ag==",
1657 |       "dependencies": {
1658 |         "heap": "0.2.5"
1659 |       }
1660 |     },
1661 |     "node_modules/perfect-debounce": {
1662 |       "version": "2.1.0",
1663 |       "resolved": "https://registry.npmmirror.com/perfect-debounce/-/perfect-debounce-2.1.0.tgz",
1664 |       "integrity": "sha512-LjgdTytVFXeUgtHZr9WYViYSM/g8MkcTPYDlPa3cDqMirHjKiSZPYd6DoL7pK8AJQr+uWkQvCjHNdiMqsrJs+g==",
1665 |       "license": "MIT"
1666 |     },
1667 |     "node_modules/picocolors": {
1668 |       "version": "1.1.1",
1669 |       "resolved": "https://registry.npmmirror.com/picocolors/-/picocolors-1.1.1.tgz",
1670 |       "integrity": "sha512-xceH2snhtb5M9liqDsmEw56le376mTZkEX/jEb/RxNFyegNul7eNslCXP9FDj/Lcu0X8KEyMceP2ntpaHrDEVA==",
1671 |       "license": "ISC"
1672 |     },
1673 |     "node_modules/pinia": {
1674 |       "version": "4.0.2",
1675 |       "resolved": "https://registry.npmmirror.com/pinia/-/pinia-4.0.2.tgz",
1676 |       "integrity": "sha512-yKVVA7bSj5oRZFp/Ab9wLlmyb5gPUYEiIm4ryiWTe/xe7PtkRdMVOp1X1ggvq0c6Uj7Q0Du1HnV2mtAwM0Ks1g==",
1677 |       "license": "MIT",
1678 |       "dependencies": {
1679 |         "nostics": "^1.1.4"
1680 |       },
1681 |       "funding": {
1682 |         "url": "https://github.com/sponsors/posva"
1683 |       },
1684 |       "peerDependencies": {
1685 |         "@vue/devtools-api": "^8.1.5",
1686 |         "typescript": ">=5.6.0",
1687 |         "vue": "^3.5.11"
1688 |       },
1689 |       "peerDependenciesMeta": {
1690 |         "@vue/devtools-api": {
1691 |           "optional": false
1692 |         },
1693 |         "typescript": {
1694 |           "optional": true
1695 |         }
1696 |       }
1697 |     },
1698 |     "node_modules/postcss": {
1699 |       "version": "8.5.24",
1700 |       "resolved": "https://registry.npmmirror.com/postcss/-/postcss-8.5.24.tgz",
1701 |       "integrity": "sha512-8RyVklq0owXUTa4xlpzu4l9AaVKIdQvAcOHZWaMh98HgySsUtxRVf/chRe3dsSLqb6i40BzGRzEUddRaI+9TSw==",
1702 |       "funding": [
1703 |         {
1704 |           "type": "opencollective",
1705 |           "url": "https://opencollective.com/postcss/"
1706 |         },
1707 |         {
1708 |           "type": "tidelift",
1709 |           "url": "https://tidelift.com/funding/github/npm/postcss"
1710 |         },
1711 |         {
1712 |           "type": "github",
1713 |           "url": "https://github.com/sponsors/ai"
1714 |         }
1715 |       ],
1716 |       "license": "MIT",
1717 |       "dependencies": {
1718 |         "nanoid": "^3.3.16",
1719 |         "picocolors": "^1.1.1",
1720 |         "source-map-js": "^1.2.1"
1721 |       },
1722 |       "engines": {
1723 |         "node": "^10 || ^12 || >=14"
1724 |       }
1725 |     },
1726 |     "node_modules/proxy-from-env": {
1727 |       "version": "2.1.0",
1728 |       "resolved": "https://registry.npmmirror.com/proxy-from-env/-/proxy-from-env-2.1.0.tgz",
1729 |       "integrity": "sha512-cJ+oHTW1VAEa8cJslgmUZrc+sjRKgAKl3Zyse6+PV38hZe/V6Z14TbCuXcan9F9ghlz4QrFr2c92TNF82UkYHA==",
1730 |       "license": "MIT",
1731 |       "engines": {
1732 |         "node": ">=10"
1733 |       }
1734 |     },
1735 |     "node_modules/rollup": {
1736 |       "version": "4.62.3",
1737 |       "resolved": "https://registry.npmmirror.com/rollup/-/rollup-4.62.3.tgz",
1738 |       "integrity": "sha512-Gu0c0iH9FzgX1L1t7ByIbbS3Vmdz+6KHm/EsqmmC71gUQ82yvZRkTK6XzrFObSka91WUVdynqp6nsfilzr5k6Q==",
1739 |       "dev": true,
1740 |       "license": "MIT",
1741 |       "dependencies": {
1742 |         "@types/estree": "1.0.9"
1743 |       },
1744 |       "bin": {
1745 |         "rollup": "dist/bin/rollup"
1746 |       },
1747 |       "engines": {
1748 |         "node": ">=18.0.0",
1749 |         "npm": ">=8.0.0"
1750 |       },
1751 |       "optionalDependencies": {
1752 |         "@rollup/rollup-android-arm-eabi": "4.62.3",
1753 |         "@rollup/rollup-android-arm64": "4.62.3",
1754 |         "@rollup/rollup-darwin-arm64": "4.62.3",
1755 |         "@rollup/rollup-darwin-x64": "4.62.3",
1756 |         "@rollup/rollup-freebsd-arm64": "4.62.3",
1757 |         "@rollup/rollup-freebsd-x64": "4.62.3",
1758 |         "@rollup/rollup-linux-arm-gnueabihf": "4.62.3",
1759 |         "@rollup/rollup-linux-arm-musleabihf": "4.62.3",
1760 |         "@rollup/rollup-linux-arm64-gnu": "4.62.3",
1761 |         "@rollup/rollup-linux-arm64-musl": "4.62.3",
1762 |         "@rollup/rollup-linux-loong64-gnu": "4.62.3",
1763 |         "@rollup/rollup-linux-loong64-musl": "4.62.3",
1764 |         "@rollup/rollup-linux-ppc64-gnu": "4.62.3",
1765 |         "@rollup/rollup-linux-ppc64-musl": "4.62.3",
1766 |         "@rollup/rollup-linux-riscv64-gnu": "4.62.3",
1767 |         "@rollup/rollup-linux-riscv64-musl": "4.62.3",
1768 |         "@rollup/rollup-linux-s390x-gnu": "4.62.3",
1769 |         "@rollup/rollup-linux-x64-gnu": "4.62.3",
1770 |         "@rollup/rollup-linux-x64-musl": "4.62.3",
1771 |         "@rollup/rollup-openbsd-x64": "4.62.3",
1772 |         "@rollup/rollup-openharmony-arm64": "4.62.3",
1773 |         "@rollup/rollup-win32-arm64-msvc": "4.62.3",
1774 |         "@rollup/rollup-win32-ia32-msvc": "4.62.3",
1775 |         "@rollup/rollup-win32-x64-gnu": "4.62.3",
1776 |         "@rollup/rollup-win32-x64-msvc": "4.62.3",
1777 |         "fsevents": "~2.3.2"
1778 |       }
1779 |     },
1780 |     "node_modules/sortablejs": {
1781 |       "version": "1.14.0",
1782 |       "resolved": "https://registry.npmmirror.com/sortablejs/-/sortablejs-1.14.0.tgz",
1783 |       "integrity": "sha512-pBXvQCs5/33fdN1/39pPL0NZF20LeRbLQ5jtnheIPN9JQAaufGjKdWduZn4U7wCtVuzKhmRkI0DFYHYRbB2H1w==",
1784 |       "license": "MIT"
1785 |     },
1786 |     "node_modules/source-map-js": {
1787 |       "version": "1.2.1",
1788 |       "resolved": "https://registry.npmmirror.com/source-map-js/-/source-map-js-1.2.1.tgz",
1789 |       "integrity": "sha512-UXWMKhLOwVKb728IUtQPXxfYU+usdybtUrK/8uGE8CQMvrhOpwvzDBwj0QhSL7MQc7vIsISBG8VQ8+IDQxpfQA==",
1790 |       "license": "BSD-3-Clause",
1791 |       "engines": {
1792 |         "node": ">=0.10.0"
1793 |       }
1794 |     },
1795 |     "node_modules/splitpanes": {
1796 |       "version": "4.1.2",
1797 |       "resolved": "https://registry.npmmirror.com/splitpanes/-/splitpanes-4.1.2.tgz",
1798 |       "integrity": "sha512-frNchoCv7w0nMQEuaDGgMGMU6jv3NhN6bBGQVfCNgwJdVcYaRmi1dwYDjp7SifAoUFdiQjBRB254LJNidzo15Q==",
1799 |       "license": "MIT",
1800 |       "funding": {
1801 |         "url": "https://github.com/sponsors/antoniandre"
1802 |       },
1803 |       "peerDependencies": {
1804 |         "vue": "^3.2.0"
1805 |       }
1806 |     },
1807 |     "node_modules/vite": {
1808 |       "version": "5.4.21",
1809 |       "resolved": "https://registry.npmmirror.com/vite/-/vite-5.4.21.tgz",
1810 |       "integrity": "sha512-o5a9xKjbtuhY6Bi5S3+HvbRERmouabWbyUcpXXUA1u+GNUKoROi9byOJ8M0nHbHYHkYICiMlqxkg1KkYmm25Sw==",
1811 |       "dev": true,
1812 |       "license": "MIT",
1813 |       "dependencies": {
1814 |         "esbuild": "^0.21.3",
1815 |         "postcss": "^8.4.43",
1816 |         "rollup": "^4.20.0"
1817 |       },
1818 |       "bin": {
1819 |         "vite": "bin/vite.js"
1820 |       },
1821 |       "engines": {
1822 |         "node": "^18.0.0 || >=20.0.0"
1823 |       },
1824 |       "funding": {
1825 |         "url": "https://github.com/vitejs/vite?sponsor=1"
1826 |       },
1827 |       "optionalDependencies": {
1828 |         "fsevents": "~2.3.3"
1829 |       },
1830 |       "peerDependencies": {
1831 |         "@types/node": "^18.0.0 || >=20.0.0",
1832 |         "less": "*",
1833 |         "lightningcss": "^1.21.0",
1834 |         "sass": "*",
1835 |         "sass-embedded": "*",
1836 |         "stylus": "*",
1837 |         "sugarss": "*",
1838 |         "terser": "^5.4.0"
1839 |       },
1840 |       "peerDependenciesMeta": {
1841 |         "@types/node": {
1842 |           "optional": true
1843 |         },
1844 |         "less": {
1845 |           "optional": true
1846 |         },
1847 |         "lightningcss": {
1848 |           "optional": true
1849 |         },
1850 |         "sass": {
1851 |           "optional": true
1852 |         },
1853 |         "sass-embedded": {
1854 |           "optional": true
1855 |         },
1856 |         "stylus": {
1857 |           "optional": true
1858 |         },
1859 |         "sugarss": {
1860 |           "optional": true
1861 |         },
1862 |         "terser": {
1863 |           "optional": true
1864 |         }
1865 |       }
1866 |     },
1867 |     "node_modules/vue": {
1868 |       "version": "3.5.40",
1869 |       "resolved": "https://registry.npmmirror.com/vue/-/vue-3.5.40.tgz",
1870 |       "integrity": "sha512-+8PJ4SJXdn/cHGImF4CKdxlWHIN5Dkt7DoufRREM6h6uVCx2m7QxgcEQmmzyOK8A9mcafg7sFbJFYsdFVubTig==",
1871 |       "license": "MIT",
1872 |       "dependencies": {
1873 |         "@vue/compiler-dom": "3.5.40",
1874 |         "@vue/compiler-sfc": "3.5.40",
1875 |         "@vue/runtime-dom": "3.5.40",
1876 |         "@vue/server-renderer": "3.5.40",
1877 |         "@vue/shared": "3.5.40"
1878 |       },
1879 |       "peerDependencies": {
1880 |         "typescript": "*"
1881 |       },
1882 |       "peerDependenciesMeta": {
1883 |         "typescript": {
1884 |           "optional": true
1885 |         }
1886 |       }
1887 |     },
1888 |     "node_modules/vue-component-type-helpers": {
1889 |       "version": "3.3.8",
1890 |       "resolved": "https://registry.npmmirror.com/vue-component-type-helpers/-/vue-component-type-helpers-3.3.8.tgz",
1891 |       "integrity": "sha512-troqCMmQodQDqUqn63NQaFi+CDSclSe7sc8VEBFqf5GFLqmGR2Ph3P2WEC7qwpRVyEWsTi/aAr4vyOe/B1hU3g==",
1892 |       "license": "MIT"
1893 |     },
1894 |     "node_modules/vuedraggable": {
1895 |       "version": "4.1.0",
1896 |       "resolved": "https://registry.npmmirror.com/vuedraggable/-/vuedraggable-4.1.0.tgz",
1897 |       "integrity": "sha512-FU5HCWBmsf20GpP3eudURW3WdWTKIbEIQxh9/8GE806hydR9qZqRRxRE3RjqX7PkuLuMQG/A7n3cfj9rCEchww==",
1898 |       "license": "MIT",
1899 |       "dependencies": {
1900 |         "sortablejs": "1.14.0"
1901 |       },
1902 |       "peerDependencies": {
1903 |         "vue": "^3.0.1"
1904 |       }
1905 |     }
1906 |   }
1907 | }
```

## File: D:\PycharmProjects\Easycode\frontend\package.json

- Extension: .json
- Language: json
- Size: 567 bytes
- Created: 2026-07-28 20:03:07
- Modified: 2026-08-06 12:31:56

### Code

```json
 1 | {
 2 |   "name": "frontend",
 3 |   "version": "0.0.0",
 4 |   "private": true,
 5 |   "scripts": {
 6 |     "dev": "vite",
 7 |     "build": "vite build",
 8 |     "preview": "vite preview"
 9 |   },
10 |   "dependencies": {
11 |     "@element-plus/icons-vue": "^2.3.2",
12 |     "axios": "^1.7.0",
13 |     "element-plus": "^2.8.0",
14 |     "lucide-vue-next": "^0.577.0",
15 |     "pathfinding": "^0.4.18",
16 |     "pinia": "^4.0.2",
17 |     "splitpanes": "^4.1.2",
18 |     "vue": "^3.4.0",
19 |     "vuedraggable": "^4.1.0"
20 |   },
21 |   "devDependencies": {
22 |     "@vitejs/plugin-vue": "^5.0.4",
23 |     "@vue/devtools-api": "^8.2.1",
24 |     "vite": "^5.0.0"
25 |   }
26 | }
```

## File: D:\PycharmProjects\Easycode\frontend\README.md

- Extension: .md
- Language: markdown
- Size: 1025 bytes
- Created: 2026-07-28 20:03:07
- Modified: 2026-07-28 20:03:07

### Code

```markdown
 1 | # frontend
 2 | 
 3 | This template should help get you started developing with Vue 3 in Vite.
 4 | 
 5 | ## Recommended IDE Setup
 6 | 
 7 | [VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).
 8 | 
 9 | ## Recommended Browser Setup
10 | 
11 | - Chromium-based browsers (Chrome, Edge, Brave, etc.):
12 |   - [Vue.js devtools](https://chromewebstore.google.com/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd)
13 |   - [Turn on Custom Object Formatter in Chrome DevTools](http://bit.ly/object-formatters)
14 | - Firefox:
15 |   - [Vue.js devtools](https://addons.mozilla.org/en-US/firefox/addon/vue-js-devtools/)
16 |   - [Turn on Custom Object Formatter in Firefox DevTools](https://fxdx.dev/firefox-devtools-custom-object-formatters/)
17 | 
18 | ## Customize configuration
19 | 
20 | See [Vite Configuration Reference](https://vite.dev/config/).
21 | 
22 | ## Project Setup
23 | 
24 | ```sh
25 | npm install
26 | ```
27 | 
28 | ### Compile and Hot-Reload for Development
29 | 
30 | ```sh
31 | npm run dev
32 | ```
33 | 
34 | ### Compile and Minify for Production
35 | 
36 | ```sh
37 | npm run build
38 | ```
```

## File: D:\PycharmProjects\Easycode\frontend\vite.config.js

- Extension: .js
- Language: javascript
- Size: 528 bytes
- Created: 2026-07-28 20:03:07
- Modified: 2026-08-03 17:56:50

### Code

```javascript
 1 | // frontend/vite.config.js
 2 | import { fileURLToPath, URL } from 'node:url'
 3 | import { defineConfig } from 'vite'
 4 | import vue from '@vitejs/plugin-vue'
 5 | 
 6 | export default defineConfig({
 7 |     plugins: [vue()],
 8 |     resolve: {
 9 |         alias: {
10 |             '@': fileURLToPath(new URL('./src', import.meta.url))
11 |         }
12 |     },
13 |     server: {
14 |         host: '0.0.0.0',
15 |         port: 5173,
16 |         proxy: {
17 |             '/api': {
18 |                 target: 'http://127.0.0.1:8000',
19 |                 changeOrigin: true
20 |             }
21 |         }
22 |     }
23 | })
```

## File: D:\PycharmProjects\Easycode\frontend\.vs\VSWorkspaceState.json

- Extension: .json
- Language: json
- Size: 346 bytes
- Created: 2026-08-01 22:41:19
- Modified: 2026-08-11 22:31:21

### Code

```json
 1 | {
 2 |   "ExpandedNodes": [
 3 |     "",
 4 |     "\\src",
 5 |     "\\src\\api",
 6 |     "\\src\\components",
 7 |     "\\src\\components\\panels",
 8 |     "\\src\\composables",
 9 |     "\\src\\config",
10 |     "\\src\\layouts",
11 |     "\\src\\stores",
12 |     "\\src\\utils"
13 |   ],
14 |   "SelectedNode": "\\src\\components\\WorkflowCanvas.vue",
15 |   "PreviewInSolutionExplorer": false
16 | }
```

## File: D:\PycharmProjects\Easycode\frontend\src\App.vue

- Extension: .vue
- Language: unknown
- Size: 6017 bytes
- Created: 2026-07-31 13:34:12
- Modified: 2026-08-10 17:27:11

### Code

```unknown
  1 | <!-- frontend/src/App.vue -->
  2 | <template>
  3 |     <div id="app" @contextmenu.prevent>
  4 |         <!-- 主界面：直接挂载新一代 IDE 骨架布局 -->
  5 |         <template v-if="store.currentProjectPath && projectLoaded">
  6 |             <IdeLayout />
  7 |         </template>
  8 | 
  9 |         <!-- 欢迎界面（无项目或加载失败） -->
 10 |         <div v-else class="welcome">
 11 |             <div class="welcome-content">
 12 |                 <h1>⚡ Easycode 自动化工作台</h1>
 13 |                 <p>请选择并打开一个项目文件夹以开始编排</p>
 14 | 
 15 |                 <div v-if="cachedPath" class="cached-hint">
 16 |                     <el-icon><InfoFilled /></el-icon>
 17 |                     <span>上次打开：{{ cachedPath }}</span>
 18 |                 </div>
 19 | 
 20 |                 <div class="open-section">
 21 |                     <el-input v-model="projectPathInput"
 22 |                               placeholder="输入项目绝对路径，如 D:/MyProjects/demo"
 23 |                               style="width: 500px;"
 24 |                               clearable
 25 |                               @keyup.enter="handleOpenProject" />
 26 |                     <div style="margin-top: 12px;">
 27 |                         <el-button type="primary" size="large" @click="handleOpenProject">
 28 |                             📂 打开项目
 29 |                         </el-button>
 30 |                     </div>
 31 |                 </div>
 32 | 
 33 |                 <div v-if="store.recentProjects.length" class="recent">
 34 |                     <span>最近打开：</span>
 35 |                     <el-link v-for="p in store.recentProjects"
 36 |                              :key="p.path"
 37 |                              style="margin: 0 8px;"
 38 |                              @click="handleOpenRecent(p.path)">
 39 |                         {{ p.name }}
 40 |                     </el-link>
 41 |                 </div>
 42 |             </div>
 43 |         </div>
 44 |     </div>
 45 | </template>
 46 | 
 47 | <script setup>
 48 |     import { ref, onMounted, computed } from 'vue'
 49 |     import { useMainStore } from '@/stores'
 50 |     import { ElMessage } from 'element-plus'
 51 |     import { InfoFilled } from '@element-plus/icons-vue'
 52 |     import IdeLayout from '@/layouts/IdeLayout.vue'
 53 | 
 54 |     const store = useMainStore()
 55 |     const projectPathInput = ref('')
 56 |     const projectLoaded = ref(false)
 57 | 
 58 |     const cachedPath = computed(() => store.currentProjectPath || '')
 59 | 
 60 |     // 统一的项目加载入口函数
 61 |     const loadProject = async (path) => {
 62 |         if (!path) return false
 63 |         try {
 64 |             await store.loadProjectByPath(path)
 65 |             projectLoaded.value = true
 66 |             return true
 67 |         } catch (err) {
 68 |             ElMessage.error('打开项目失败: ' + (err.message || '路径无效或文件缺失'))
 69 |             projectLoaded.value = false
 70 |             return false
 71 |         }
 72 |     }
 73 | 
 74 |     // 手动输入路径并打开
 75 |     const handleOpenProject = async () => {
 76 |         const path = projectPathInput.value.trim()
 77 |         if (!path) {
 78 |             return ElMessage.warning('请输入项目路径')
 79 |         }
 80 |         const ok = await loadProject(path)
 81 |         if (ok) {
 82 |             projectPathInput.value = ''
 83 |             ElMessage.success(`已打开项目: ${store.currentProjectName}`)
 84 |         }
 85 |     }
 86 | 
 87 |     // 点击“最近打开”历史列表
 88 |     const handleOpenRecent = async (path) => {
 89 |         const ok = await loadProject(path)
 90 |         if (ok) {
 91 |             ElMessage.success(`已打开项目: ${store.currentProjectName}`)
 92 |         } else {
 93 |             // 若打开失败，从最近打开列表中剔除失效项目
 94 |             store.recentProjects = store.recentProjects.filter(p => p.path !== path)
 95 |             localStorage.setItem('recentProjects', JSON.stringify(store.recentProjects))
 96 |         }
 97 |     }
 98 | 
 99 |     // 页面挂载初始化
100 |     onMounted(async () => {
101 |         await store.loadParams()
102 |         if (store.currentProjectPath) {
103 |             projectPathInput.value = store.currentProjectPath
104 |             const ok = await loadProject(store.currentProjectPath)
105 |             if (ok) {
106 |                 ElMessage.success(`已自动加载项目: ${store.currentProjectName}`)
107 |             } else {
108 |                 ElMessage.warning('自动加载项目失败，请检查路径')
109 |                 store.currentProjectPath = null
110 |                 projectLoaded.value = false
111 |             }
112 |         }
113 |     })
114 | </script>
115 | 
116 | <style>
117 |     * {
118 |         margin: 0;
119 |         padding: 0;
120 |         box-sizing: border-box;
121 |     }
122 | 
123 |     html, body, #app {
124 |         height: 100%;
125 |         overflow: hidden;
126 |         font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
127 |         background-color: var(--el-bg-color-page);
128 |     }
129 | 
130 |     #app {
131 |         display: flex;
132 |         flex-direction: column;
133 |         background: var(--el-bg-color-page);
134 |     }
135 | 
136 |     .welcome {
137 |         flex: 1;
138 |         display: flex;
139 |         align-items: center;
140 |         justify-content: center;
141 |         background: var(--el-bg-color-page);
142 |         color: var(--el-text-color-primary);
143 |     }
144 | 
145 |     .welcome-content {
146 |         text-align: center;
147 |     }
148 | 
149 |         .welcome-content h1 {
150 |             font-size: 48px;
151 |             margin-bottom: 16px;
152 |         }
153 | 
154 |         .welcome-content p {
155 |             font-size: 18px;
156 |             color: var(--el-text-color-secondary);
157 |             margin-bottom: 30px;
158 |         }
159 | 
160 |     .open-section {
161 |         display: flex;
162 |         flex-direction: column;
163 |         align-items: center;
164 |     }
165 | 
166 |     .cached-hint {
167 |         display: flex;
168 |         align-items: center;
169 |         gap: 6px;
170 |         color: var(--el-text-color-secondary);
171 |         font-size: 14px;
172 |         margin-bottom: 12px;
173 |     }
174 | 
175 |         .cached-hint .el-icon {
176 |             color: var(--el-color-primary);
177 |         }
178 | 
179 |     .recent {
180 |         margin-top: 30px;
181 |         font-size: 14px;
182 |         color: var(--el-text-color-secondary);
183 |     }
184 | 
185 |         .recent .el-link {
186 |             color: var(--el-color-primary);
187 |         }
188 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\main.js

- Extension: .js
- Language: javascript
- Size: 706 bytes
- Created: 2026-07-28 20:03:07
- Modified: 2026-08-03 15:49:33

### Code

```javascript
 1 | // main.js
 2 | import { createApp } from 'vue'
 3 | import { createPinia } from 'pinia'
 4 | import ElementPlus from 'element-plus'
 5 | import 'element-plus/dist/index.css'
 6 | import * as ElementPlusIconsVue from '@element-plus/icons-vue'
 7 | import App from './App.vue'
 8 | import { piniaLoggerPlugin } from './stores/plugins/loggerPlugin'
 9 | 
10 | // ⭐ 引入全局暗黑高级自定义样式表（放在 element-plus/dist/index.css 之后，覆盖默认样式）
11 | import '@/assets/theme.css'
12 | 
13 | const app = createApp(App)
14 | 
15 | for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
16 |     app.component(key, component)
17 | }
18 | 
19 | const pinia = createPinia()
20 | pinia.use(piniaLoggerPlugin)
21 | 
22 | app.use(pinia)
23 | app.use(ElementPlus)
24 | app.mount('#app')
```

## File: D:\PycharmProjects\Easycode\frontend\src\api\blueprintApi.js

- Extension: .js
- Language: javascript
- Size: 1660 bytes
- Created: 2026-08-08 21:05:18
- Modified: 2026-08-08 21:06:31

### Code

```javascript
 1 | // frontend/src/api/blueprintApi.js
 2 | import client from './client'
 3 | 
 4 | export const blueprintApi = {
 5 |     getParams: () => client.get('/api/params'),
 6 |     verifyProject: (projectPath) => client.get('/api/projects/verify', { params: { project_path: projectPath } }),
 7 |     getBlueprint: (projectPath) => client.get('/api/blueprint', { params: { project_path: projectPath } }),
 8 |     saveBlueprint: (projectPath, blueprintData) => client.post('/api/blueprint/save', { project_path: projectPath, blueprint_data: blueprintData }),
 9 |     listTasks: (projectPath) => client.get('/api/tasks', { params: { project_path: projectPath } }),
10 |     getTask: (taskId, projectPath) => client.get(`/api/tasks/${taskId}`, { params: { project_path: projectPath } }),
11 |     saveTask: (taskId, projectPath, taskData) => client.put(`/api/tasks/${taskId}`, { project_path: projectPath, task_data: taskData }),
12 |     createTask: (projectPath, taskData) => client.post('/api/tasks', { project_path: projectPath, task_data: taskData }),
13 |     deleteTask: (taskId, projectPath) => client.delete(`/api/tasks/${taskId}`, { params: { project_path: projectPath } }),
14 |     getTaskNodes: (taskId, projectPath) => client.get(`/api/tasks/${taskId}/nodes`, { params: { project_path: projectPath } }),
15 |     saveTaskOrder: (projectPath, order) => client.post('/api/tasks/order', { project_path: projectPath, order }),
16 |     runTask: (projectPath, taskId, startNodeId, blueprintData) => client.post('/api/run', { project_path: projectPath, task_id: taskId, start_node_id: startNodeId, blueprint_data: blueprintData }),
17 |     getExecutionStatus: (executionId) => client.get(`/api/execution/${executionId}`)
18 | }
```

## File: D:\PycharmProjects\Easycode\frontend\src\api\visionApi.js

- Extension: .js
- Language: javascript
- Size: 1269 bytes
- Created: 2026-08-08 21:05:33
- Modified: 2026-08-08 21:06:43

### Code

```javascript
 1 | // frontend/src/api/visionApi.js
 2 | import client from './client'
 3 | 
 4 | export const visionApi = {
 5 |     getTemplatesTree: (projectPath) => client.get('/api/templates/tree', { params: { project_path: projectPath } }),
 6 |     getTemplatePreview: (projectPath, relativePath) => client.get('/api/templates/preview', { params: { project_path: projectPath, relative_path: relativePath } }),
 7 |     createTemplateFolder: (projectPath, parentPath, folderName) => client.post('/api/templates/mkdir', { project_path: projectPath, parent_path: parentPath, folder_name: folderName }),
 8 |     getRegions: (projectPath) => client.get('/api/regions', { params: { project_path: projectPath } }),
 9 |     saveRegion: (projectPath, templateName, cropRect) => client.post('/api/regions', { project_path: projectPath, template_name: templateName, crop_rect: cropRect }),
10 |     testOcr: (projectPath, regionValue, grayScale, grayThreshold) => client.post('/api/ocr/test', { project_path: projectPath, region_value: regionValue, gray_scale: grayScale, gray_threshold: grayThreshold }),
11 |     testImage: (projectPath, templateName, grayScale, grayThreshold) => client.post('/api/image/test', { project_path: projectPath, template_name: templateName, gray_scale: grayScale, gray_threshold: grayThreshold })
12 | }
```

## File: D:\PycharmProjects\Easycode\frontend\src\api\workspaceApi.js

- Extension: .js
- Language: javascript
- Size: 670 bytes
- Created: 2026-08-08 21:05:25
- Modified: 2026-08-08 21:06:37

### Code

```javascript
 1 | // frontend/src/api/workspaceApi.js
 2 | import client from './client'
 3 | 
 4 | export const workspaceApi = {
 5 |     getWindows: () => client.get('/api/windows'),
 6 |     getContext: (projectPath) => client.get('/api/context', { params: { project_path: projectPath } }),
 7 |     saveContext: (projectPath, context) => client.post('/api/context', { project_path: projectPath, context }),
 8 |     getFullScreenshot: (projectPath) => client.get('/api/screenshot/full', { params: { project_path: projectPath } }),
 9 |     cropScreenshot: (projectPath, templateName, cropRect) => client.post('/api/screenshot/crop', { project_path: projectPath, template_name: templateName, crop_rect: cropRect })
10 | }
```

## File: D:\PycharmProjects\Easycode\frontend\src\assets\theme.css

- Extension: .css
- Language: unknown
- Size: 5690 bytes
- Created: 2026-08-03 15:49:03
- Modified: 2026-08-12 12:13:38

### Code

```unknown
  1 | ﻿/* frontend/src/assets/theme.css */
  2 | /* ==========================================================================
  3 |    ⚡ Easycode 全局暗黑主题样式表 (Deep Indigo Theme & Design Tokens)
  4 |    ========================================================================== */
  5 | :root {
  6 |     /* 核心背景色系 */
  7 |     --el-bg-color-page: #1f2033 !important;
  8 |     --el-bg-color: #26283d !important;
  9 |     --el-bg-color-overlay: #26283d !important;
 10 |     --el-fill-color-blank: #181926 !important;
 11 |     --el-fill-color: #1d1e30 !important;
 12 |     --el-fill-color-light: #2a2c45 !important;
 13 |     --el-fill-color-lighter: #313352 !important;
 14 |     /* 文本色系 */
 15 |     --el-text-color-primary: #ffffff !important;
 16 |     --el-text-color-regular: #cfd3e6 !important;
 17 |     --el-text-color-secondary: #8c8fa8 !important;
 18 |     --el-text-color-placeholder: #5c5f78 !important;
 19 |     /* 边框与主题色 */
 20 |     --el-border-color: transparent !important;
 21 |     --el-border-color-light: #313352 !important;
 22 |     --el-border-color-lighter: #282a44 !important;
 23 |     --el-color-primary: #4ed19c !important;
 24 |     --el-mask-color: rgba(15, 16, 26, 0.8) !important;
 25 |     /* ⚡ Design Tokens (设计令牌收敛) */
 26 |     --app-btn-secondary-bg: #26283d;
 27 |     --app-btn-secondary-border: #313352;
 28 |     --app-btn-secondary-hover-bg: #2b2d3d;
 29 |     --app-btn-secondary-hover-border: #4ed19c;
 30 |     --app-card-bg: #181926;
 31 |     --app-card-border: #313352;
 32 |     --app-radius-sm: 4px;
 33 |     --app-radius-md: 8px;
 34 |     --app-radius-lg: 12px;
 35 | }
 36 | 
 37 | /* --------------------------------------------------------------------------
 38 |    【通用按钮与卡片样式收敛】
 39 |    -------------------------------------------------------------------------- */
 40 | /* 次级操作按钮 (图标 + 文字深灰圆角矩形) */
 41 | .app-btn-secondary {
 42 |     background-color: var(--app-btn-secondary-bg) !important;
 43 |     border: 1px solid var(--app-btn-secondary-border) !important;
 44 |     color: var(--el-text-color-regular) !important;
 45 |     border-radius: var(--app-radius-sm) !important;
 46 |     padding: 4px 12px !important;
 47 |     height: 32px !important;
 48 |     font-size: 12px !important;
 49 |     font-weight: 500 !important;
 50 |     display: inline-flex;
 51 |     align-items: center;
 52 |     gap: 6px;
 53 |     cursor: pointer;
 54 |     transition: all 0.2s ease;
 55 |     user-select: none;
 56 | }
 57 | 
 58 |     .app-btn-secondary:hover {
 59 |         background-color: var(--app-btn-secondary-hover-bg) !important;
 60 |         border-color: var(--app-btn-secondary-hover-border) !important;
 61 |         color: var(--el-color-primary) !important;
 62 |     }
 63 | 
 64 | .app-btn-icon {
 65 |     width: 14px !important;
 66 |     height: 14px !important;
 67 |     color: currentColor !important;
 68 |     flex-shrink: 0;
 69 | }
 70 | 
 71 | /* 通用暗色面板卡片 */
 72 | .app-card-dark {
 73 |     background: var(--app-card-bg);
 74 |     border: 1px solid var(--app-card-border);
 75 |     border-radius: var(--app-radius-md);
 76 |     padding: 12px;
 77 |     transition: all 0.2s ease;
 78 | }
 79 | 
 80 |     .app-card-dark:hover {
 81 |         border-color: var(--el-color-primary);
 82 |     }
 83 | 
 84 | /* --------------------------------------------------------------------------
 85 |    【布局标准化与全局重置】
 86 |    -------------------------------------------------------------------------- */
 87 | html, body, #app {
 88 |     background-color: var(--el-bg-color-page) !important;
 89 |     color: var(--el-text-color-primary) !important;
 90 |     font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif !important;
 91 |     margin: 0;
 92 |     padding: 0;
 93 |     height: 100%;
 94 |     width: 100%;
 95 |     overflow: hidden;
 96 |     cursor: default;
 97 |     user-select: none;
 98 | }
 99 | 
100 | input, textarea, [contenteditable="true"], .log-content, .el-input__inner, .el-textarea__inner {
101 |     cursor: text !important;
102 |     user-select: text !important;
103 | }
104 | 
105 | *, *::before, *::after {
106 |     box-sizing: border-box !important;
107 | }
108 | 
109 | /* 细窄美化滚动条 */
110 | ::-webkit-scrollbar {
111 |     width: 6px;
112 |     height: 6px;
113 | }
114 | 
115 | ::-webkit-scrollbar-track {
116 |     background: var(--el-bg-color-page);
117 | }
118 | 
119 | ::-webkit-scrollbar-thumb {
120 |     background: #353757;
121 |     border-radius: 3px;
122 | }
123 | 
124 |     ::-webkit-scrollbar-thumb:hover {
125 |         background: var(--el-color-primary);
126 |     }
127 | 
128 | /* --------------------------------------------------------------------------
129 |    【表单与弹窗覆盖】
130 |    -------------------------------------------------------------------------- */
131 | .el-input,
132 | .el-select,
133 | .el-input__wrapper,
134 | .el-textarea__inner,
135 | .el-select .el-input__wrapper {
136 |     background-color: var(--el-fill-color-blank) !important;
137 |     box-shadow: none !important;
138 |     border: 1px solid transparent !important;
139 |     border-radius: var(--app-radius-md) !important;
140 |     transition: all 0.2s ease !important;
141 | }
142 | 
143 |     .el-input__inner,
144 |     .el-textarea__inner,
145 |     .el-select .el-input__inner {
146 |         color: var(--el-text-color-primary) !important;
147 |         font-weight: 500;
148 |         background-color: transparent !important;
149 |     }
150 | 
151 |         .el-input__wrapper:hover,
152 |         .el-textarea__inner:hover,
153 |         .el-select .el-input__wrapper:hover,
154 |         .el-input__wrapper.is-focus,
155 |         .el-textarea__inner:focus,
156 |         .el-select .el-input__wrapper.is-focused {
157 |             border-color: var(--el-color-primary) !important;
158 |         }
159 | 
160 | .el-dialog,
161 | .el-message-box,
162 | .el-popover.el-popper {
163 |     background-color: var(--el-bg-color-overlay) !important;
164 |     border: 1px solid #353757 !important;
165 |     border-radius: var(--app-radius-lg) !important;
166 |     box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5) !important;
167 | }
168 | 
169 | .el-dialog__title,
170 | .el-message-box__title {
171 |     color: var(--el-text-color-primary) !important;
172 |     font-weight: 600;
173 |     font-size: 16px;
174 | }
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\AppFooter.vue

- Extension: .vue
- Language: unknown
- Size: 3886 bytes
- Created: 2026-07-28 21:29:03
- Modified: 2026-08-08 21:20:06

### Code

```unknown
  1 | <!-- frontend/src/components/AppFooter.vue -->
  2 | <template>
  3 |     <footer class="app-footer">
  4 |         <div class="footer-left">
  5 |             <span>● 就绪 | 项目: {{ currentProject }}</span>
  6 |         </div>
  7 | 
  8 |         <div class="footer-center">
  9 |             <span class="panel-status" @click="dialogVisible = true">
 10 |                 <el-icon><Monitor /></el-icon>
 11 |                 {{ panelStatus }}
 12 |             </span>
 13 |         </div>
 14 | 
 15 |         <div class="footer-right">
 16 |             <div class="footer-tab-btn"
 17 |                  :class="{ 'is-active': store.minimapExpanded }"
 18 |                  @click="store.toggleMinimap">
 19 |                 <span>🗺️ 全景导航</span>
 20 |             </div>
 21 |             <div class="footer-tab-btn"
 22 |                  :class="{ 'is-active': store.logExpanded }"
 23 |                  @click="store.toggleLogPanel">
 24 |                 <span>📝 运行日志</span>
 25 |             </div>
 26 |             <span class="exec-status">⚡ 执行状态: 空闲</span>
 27 |         </div>
 28 | 
 29 |         <PanelSettingsDialog v-model:visible="dialogVisible"
 30 |                              @apply="handleApplyContext" />
 31 |     </footer>
 32 | </template>
 33 | 
 34 | <script setup>
 35 |     import { ref, computed } from 'vue'
 36 |     import { useMainStore } from '@/stores'
 37 |     import { ElMessage } from 'element-plus'
 38 |     import { Monitor } from '@element-plus/icons-vue'
 39 |     import PanelSettingsDialog from './PanelSettingsDialog.vue'
 40 | 
 41 |     const store = useMainStore()
 42 |     const dialogVisible = ref(false)
 43 | 
 44 |     const currentProject = computed(() => store.currentProjectName || '未选择')
 45 | 
 46 |     const panelStatus = computed(() => {
 47 |         const ctx = store.currentContext
 48 |         if (ctx && ctx.windowTitle) {
 49 |             const label = ctx.isEmulator ? '📱' : '🪟'
 50 |             return `${label} 工作面板：${ctx.windowTitle}`
 51 |         }
 52 |         return '🖥️ 工作面板：Windows 桌面'
 53 |     })
 54 | 
 55 |     const handleApplyContext = async (context) => {
 56 |         try {
 57 |             await store.setCurrentContext(context)
 58 |             ElMessage.success('工作面板已更新并保存')
 59 |         } catch (err) {
 60 |             ElMessage.error('保存失败: ' + err.message)
 61 |         }
 62 |     }
 63 | </script>
 64 | 
 65 | <style scoped>
 66 |     .app-footer {
 67 |         height: 30px;
 68 |         display: flex;
 69 |         align-items: center;
 70 |         justify-content: space-between;
 71 |         padding: 0 20px;
 72 |         background: var(--el-bg-color);
 73 |         border-top: 1px solid var(--el-border-color-light);
 74 |         color: var(--el-text-color-secondary);
 75 |         font-size: 12px;
 76 |         flex-shrink: 0;
 77 |         z-index: 1000;
 78 |         user-select: none;
 79 |     }
 80 | 
 81 |     .footer-left, .footer-center, .footer-right {
 82 |         display: flex;
 83 |         align-items: center;
 84 |         gap: 12px;
 85 |         height: 100%;
 86 |     }
 87 | 
 88 |     .panel-status {
 89 |         cursor: pointer;
 90 |         padding: 2px 10px;
 91 |         border-radius: 12px;
 92 |         background: var(--el-fill-color-blank);
 93 |         transition: background 0.2s;
 94 |     }
 95 | 
 96 |         .panel-status:hover {
 97 |             background: var(--el-fill-color-light);
 98 |         }
 99 | 
100 |         .panel-status .el-icon {
101 |             margin-right: 4px;
102 |         }
103 | 
104 |     .footer-tab-btn {
105 |         padding: 0 10px;
106 |         height: 100%;
107 |         display: flex;
108 |         align-items: center;
109 |         cursor: pointer;
110 |         transition: all 0.2s ease;
111 |         color: var(--el-text-color-secondary);
112 |         border-radius: 3px;
113 |     }
114 | 
115 |         .footer-tab-btn:hover {
116 |             background: rgba(255, 255, 255, 0.05);
117 |             color: var(--el-text-color-primary);
118 |         }
119 | 
120 |         .footer-tab-btn.is-active {
121 |             background: rgba(78, 209, 156, 0.15);
122 |             color: var(--el-color-primary, #4ed19c);
123 |             font-weight: 600;
124 |             border-bottom: 2px solid var(--el-color-primary, #4ed19c);
125 |         }
126 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\AppHeader.vue

- Extension: .vue
- Language: unknown
- Size: 4900 bytes
- Created: 2026-07-31 13:34:12
- Modified: 2026-08-08 21:19:55

### Code

```unknown
  1 | <!-- frontend/src/components/AppHeader.vue -->
  2 | <template>
  3 |     <header class="app-header">
  4 |         <div class="left-group">
  5 |             <el-icon class="menu-icon"><Menu /></el-icon>
  6 |             <span class="logo">⚡ 节点自动化</span>
  7 |         </div>
  8 | 
  9 |         <div class="project-selector">
 10 |             <span class="project-name">📁 {{ store.currentProjectName || '未选择项目' }}</span>
 11 |             <el-button size="small" type="primary" @click="switchProject">
 12 |                 🔄 切换
 13 |             </el-button>
 14 |         </div>
 15 | 
 16 |         <el-menu mode="horizontal"
 17 |                  :default-active="activeMenu"
 18 |                  background-color="#2d2d44"
 19 |                  text-color="#cfd3e6"
 20 |                  active-text-color="#409EFF"
 21 |                  class="menu-bar"
 22 |                  @select="onMenuSelect">
 23 |             <el-menu-item index="file">文件</el-menu-item>
 24 |             <el-menu-item index="edit">编辑</el-menu-item>
 25 |             <el-menu-item index="view">视图</el-menu-item>
 26 |             <el-menu-item index="screenshot" @click="openScreenshot">截图工具</el-menu-item>
 27 |             <el-menu-item index="run">运行</el-menu-item>
 28 |         </el-menu>
 29 | 
 30 |         <div class="header-actions">
 31 |             <el-button type="primary" size="small" @click="runTask">▶ 运行</el-button>
 32 |         </div>
 33 | 
 34 |         <ScreenshotTool ref="screenshotToolRef" />
 35 |     </header>
 36 | </template>
 37 | 
 38 | <script setup>
 39 |     import { ref } from 'vue'
 40 |     import { Menu } from '@element-plus/icons-vue'
 41 |     import { useMainStore } from '@/stores'
 42 |     import { ElMessage, ElMessageBox } from 'element-plus'
 43 |     import ScreenshotTool from './ScreenshotTool.vue'
 44 | 
 45 |     const store = useMainStore()
 46 |     const activeMenu = ref('file')
 47 |     const screenshotToolRef = ref(null)
 48 | 
 49 |     const switchProject = async () => {
 50 |         try {
 51 |             const { value: path } = await ElMessageBox.prompt('请输入新的项目完整路径', '切换项目', {
 52 |                 confirmButtonText: '确定',
 53 |                 cancelButtonText: '取消',
 54 |                 inputValue: store.currentProjectPath || '',
 55 |                 inputPattern: /^[a-zA-Z]:[\\/].+/,
 56 |                 inputErrorMessage: '请输入有效的绝对路径（如 D:/MyProjects/demo）'
 57 |             })
 58 |             if (path) {
 59 |                 await store.loadProjectByPath(path)
 60 |                 ElMessage.success(`已切换到项目: ${store.currentProjectName}`)
 61 |                 store.selectedNodeId = null
 62 |             }
 63 |         } catch (err) {
 64 |             if (err !== 'cancel') {
 65 |                 ElMessage.error('切换失败: ' + err.message)
 66 |             }
 67 |         }
 68 |     }
 69 | 
 70 |     const onMenuSelect = (index) => {
 71 |         activeMenu.value = index
 72 |         if (index === 'screenshot') openScreenshot()
 73 |     }
 74 | 
 75 |     const openScreenshot = () => {
 76 |         if (screenshotToolRef.value) {
 77 |             screenshotToolRef.value.open('template')
 78 |         }
 79 |     }
 80 | 
 81 |     const runTask = async () => {
 82 |         if (!store.currentTaskId) {
 83 |             ElMessage.warning('请先选择一个任务')
 84 |             return
 85 |         }
 86 |         try {
 87 |             ElMessage.info('任务执行中...')
 88 |             const result = await store.runTask(store.currentTaskId, null)
 89 |             if (result && result.status === 'started') {
 90 |                 ElMessage.success('任务已启动，请查看执行状态')
 91 |             } else {
 92 |                 ElMessage.error('执行失败')
 93 |             }
 94 |         } catch (err) {
 95 |             ElMessage.error('执行请求失败: ' + err.message)
 96 |         }
 97 |     }
 98 | </script>
 99 | 
100 | <style scoped>
101 |     .app-header {
102 |         display: flex;
103 |         align-items: center;
104 |         height: 40px;
105 |         padding: 0 12px;
106 |         background: var(--el-bg-color);
107 |         border-bottom: 1px solid var(--el-border-color-light);
108 |         flex-shrink: 0;
109 |         gap: 12px;
110 |     }
111 | 
112 |     .left-group {
113 |         display: flex;
114 |         align-items: center;
115 |         gap: 8px;
116 |     }
117 | 
118 |     .menu-icon {
119 |         color: var(--el-text-color-regular);
120 |         font-size: 20px;
121 |         cursor: pointer;
122 |     }
123 | 
124 |         .menu-icon:hover {
125 |             color: var(--el-color-primary);
126 |         }
127 | 
128 |     .logo {
129 |         color: var(--el-text-color-primary);
130 |         font-weight: bold;
131 |         font-size: 16px;
132 |     }
133 | 
134 |     .project-selector {
135 |         display: flex;
136 |         align-items: center;
137 |         gap: 8px;
138 |         flex-shrink: 0;
139 |     }
140 | 
141 |     .project-name {
142 |         color: var(--el-text-color-regular);
143 |         font-weight: 500;
144 |     }
145 | 
146 |     .menu-bar {
147 |         flex: 1;
148 |         border-bottom: none;
149 |         background: transparent !important;
150 |     }
151 | 
152 |         .menu-bar .el-menu-item {
153 |             height: 40px;
154 |             line-height: 40px;
155 |         }
156 | 
157 |     .header-actions {
158 |         display: flex;
159 |         gap: 8px;
160 |     }
161 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\FileBrowser.vue

- Extension: .vue
- Language: unknown
- Size: 16390 bytes
- Created: 2026-07-29 17:31:29
- Modified: 2026-08-11 15:07:41

### Code

```unknown
  1 | <!-- frontend/src/components/FileBrowser.vue -->
  2 | <template>
  3 |     <div class="file-browser dark-theme">
  4 |         <!-- 左侧目录树区域 -->
  5 |         <div class="tree-sidebar">
  6 |             <div class="tree-header">
  7 |                 <span>📁 文件夹目录</span>
  8 |                 <el-button type="primary" link size="small" @click="inlineCreateFolder('')">
  9 |                     ➕ 根新建
 10 |                 </el-button>
 11 |             </div>
 12 | 
 13 |             <div class="tree-wrapper">
 14 |                 <el-tree ref="treeRef"
 15 |                          :data="treeData"
 16 |                          :props="defaultProps"
 17 |                          node-key="id"
 18 |                          highlight-current
 19 |                          default-expand-all
 20 |                          :expand-on-click-node="false"
 21 |                          @node-click="handleFolderClick">
 22 |                     <template #default="{ node, data }">
 23 |                         <div class="custom-tree-node">
 24 |                             <template v-if="data.isCreating">
 25 |                                 <span class="node-icon">📁</span>
 26 |                                 <input ref="inlineInputRef"
 27 |                                        v-model="data.creatingName"
 28 |                                        class="inline-folder-input"
 29 |                                        @keyup.enter="submitInlineFolder(data)"
 30 |                                        @keyup.esc="cancelInlineFolder(data)"
 31 |                                        @blur="submitInlineFolder(data)" />
 32 |                             </template>
 33 |                             <template v-else>
 34 |                                 <span class="node-label">📁 {{ node.label }}</span>
 35 |                                 <el-button class="node-mkdir-btn"
 36 |                                            type="primary"
 37 |                                            link
 38 |                                            size="small"
 39 |                                            title="在此目录下新建子文件夹"
 40 |                                            @click.stop="inlineCreateFolder(data.id)">
 41 |                                     +
 42 |                                 </el-button>
 43 |                             </template>
 44 |                         </div>
 45 |                     </template>
 46 |                 </el-tree>
 47 |             </div>
 48 |         </div>
 49 | 
 50 |         <!-- 右侧内容与操作区 -->
 51 |         <div class="content-body">
 52 |             <div class="location-bar">
 53 |                 <span>当前选择路径: </span>
 54 |                 <strong class="path-highlight">/templates/{{ currentRelPath || '(根目录)' }}</strong>
 55 |             </div>
 56 | 
 57 |             <!-- 图片网格查看 -->
 58 |             <div class="image-grid">
 59 |                 <div v-for="img in imageList"
 60 |                      :key="img.name"
 61 |                      class="image-card"
 62 |                      :class="{ selected: selectedImage === img.name }"
 63 |                      @click="handleImageClick(img.name)"
 64 |                      @dblclick="handleImageDblClick(img.name)">
 65 |                     <div class="img-wrapper">
 66 |                         <img :src="img.data" :alt="img.name" />
 67 |                     </div>
 68 |                     <div class="image-name" :title="img.name">{{ img.name }}</div>
 69 |                 </div>
 70 |                 <div v-if="!imageList.length" class="empty-tip">
 71 |                     📂 当前目录下暂无图片，可在下方直接输入新名称保存
 72 |                 </div>
 73 |             </div>
 74 | 
 75 |             <!-- 底部保存/选择操作栏 -->
 76 |             <div v-if="mode === 'save'" class="action-footer">
 77 |                 <div class="input-group">
 78 |                     <span class="input-label">图片名称:</span>
 79 |                     <el-input v-model="saveFileName"
 80 |                               placeholder="点击图片复制名，或输入新名称"
 81 |                               clearable
 82 |                               style="width: 300px;"
 83 |                               @keyup.enter="handleSaveCheck" />
 84 |                 </div>
 85 |                 <div class="btn-group">
 86 |                     <el-button @click="$emit('close')">取消</el-button>
 87 |                     <el-button type="primary" :loading="saving" @click="handleSaveCheck">保存截图</el-button>
 88 |                 </div>
 89 |             </div>
 90 | 
 91 |             <div v-else class="action-footer">
 92 |                 <span class="tip-text">💡 单击填充名，双击直接确认选择</span>
 93 |                 <div class="btn-group">
 94 |                     <el-button type="info" @click="$emit('close')">取消</el-button>
 95 |                     <el-button type="success" :disabled="!selectedImage" @click="confirmSelect">
 96 |                         确定选择
 97 |                     </el-button>
 98 |                 </div>
 99 |             </div>
100 |         </div>
101 |     </div>
102 | </template>
103 | 
104 | <script setup>
105 |     import { ref, watch, nextTick } from 'vue'
106 |     import { ElMessage, ElMessageBox } from 'element-plus'
107 |     import { visionApi } from '@/api/visionApi'
108 | 
109 |     const props = defineProps({
110 |         projectPath: { type: String, required: true },
111 |         mode: { type: String, default: 'select' },
112 |         initialPath: { type: String, default: '' }
113 |     })
114 | 
115 |     const emit = defineEmits(['select', 'save', 'close'])
116 | 
117 |     const treeRef = ref(null)
118 |     const inlineInputRef = ref(null)
119 | 
120 |     const treeData = ref([])
121 |     const imageList = ref([])
122 |     const currentRelPath = ref('')
123 |     const selectedImage = ref('')
124 |     const saveFileName = ref('')
125 |     const saving = ref(false)
126 | 
127 |     const defaultProps = { children: 'children', label: 'name' }
128 | 
129 |     const fetchTree = async () => {
130 |         try {
131 |             if (props.initialPath) {
132 |                 try {
133 |                     await visionApi.createTemplateFolder(props.projectPath, '', props.initialPath)
134 |                 } catch {
135 |                     /* 已存在则安全忽略 */
136 |                 }
137 |             }
138 | 
139 |             const res = await visionApi.getTemplatesTree(props.projectPath)
140 |             treeData.value = [
141 |                 { name: '根目录 (templates)', id: '', children: res.tree || [] }
142 |             ]
143 | 
144 |             currentRelPath.value = props.initialPath || ''
145 |             fetchImages(currentRelPath.value)
146 |         } catch (err) {
147 |             console.error('获取目录树失败', err)
148 |         }
149 |     }
150 | 
151 |     const fetchImages = async (relPath) => {
152 |         try {
153 |             const res = await visionApi.getTemplatePreview(props.projectPath, relPath)
154 |             imageList.value = res.images || []
155 |         } catch (err) {
156 |             console.error('获取图片预览失败', err)
157 |         }
158 |     }
159 | 
160 |     const handleFolderClick = (data) => {
161 |         if (data.isCreating) return
162 |         currentRelPath.value = data.id || ''
163 |         selectedImage.value = ''
164 |         fetchImages(currentRelPath.value)
165 |     }
166 | 
167 |     const handleImageClick = (fileName) => {
168 |         const cleanName = fileName.replace(/\.png$/i, '')
169 |         selectedImage.value = fileName
170 |         if (props.mode === 'save') {
171 |             saveFileName.value = cleanName
172 |         }
173 |     }
174 | 
175 |     const handleImageDblClick = (fileName) => {
176 |         const cleanName = fileName.replace(/\.png$/i, '')
177 |         selectedImage.value = fileName
178 |         if (props.mode === 'save') {
179 |             saveFileName.value = cleanName
180 |             handleSaveCheck()
181 |         } else {
182 |             confirmSelect()
183 |         }
184 |     }
185 | 
186 |     const inlineCreateFolder = (parentPath) => {
187 |         const findParentNode = (nodes, path) => {
188 |             for (const n of nodes) {
189 |                 if (n.id === path) return n
190 |                 if (n.children) {
191 |                     const found = findParentNode(n.children, path)
192 |                     if (found) return found
193 |                 }
194 |             }
195 |             return null
196 |         }
197 | 
198 |         const parentNode = findParentNode(treeData.value, parentPath)
199 |         const targetChildren = parentNode ? (parentNode.children = parentNode.children || []) : treeData.value[0].children
200 | 
201 |         const baseName = 'New_Folder'
202 |         let defaultName = baseName
203 |         let count = 1
204 |         while (targetChildren.some(child => child.name === defaultName)) {
205 |             defaultName = `${baseName}_${count}`
206 |             count++
207 |         }
208 | 
209 |         const newNode = {
210 |             name: defaultName,
211 |             id: `temp_${Date.now()}`,
212 |             parentPath,
213 |             isCreating: true,
214 |             creatingName: defaultName
215 |         }
216 | 
217 |         targetChildren.push(newNode)
218 | 
219 |         nextTick(() => {
220 |             if (inlineInputRef.value) {
221 |                 inlineInputRef.value.focus()
222 |                 inlineInputRef.value.select()
223 |             }
224 |         })
225 |     }
226 | 
227 |     const submitInlineFolder = async (nodeData) => {
228 |         if (!nodeData.isCreating) return
229 |         const folderName = nodeData.creatingName ? nodeData.creatingName.trim() : ''
230 | 
231 |         if (!folderName) {
232 |             cancelInlineFolder(nodeData)
233 |             return
234 |         }
235 | 
236 |         nodeData.isCreating = false
237 | 
238 |         try {
239 |             await visionApi.createTemplateFolder(props.projectPath, nodeData.parentPath, folderName)
240 |             ElMessage.success(`文件夹 [${folderName}] 创建成功`)
241 |             await fetchTree()
242 |         } catch (err) {
243 |             ElMessage.error(err.message || '创建文件夹失败')
244 |             cancelInlineFolder(nodeData)
245 |         }
246 |     }
247 | 
248 |     const cancelInlineFolder = (nodeData) => {
249 |         if (!nodeData.isCreating) return
250 |         const removeNode = (nodes) => {
251 |             const idx = nodes.findIndex(n => n.id === nodeData.id)
252 |             if (idx > -1) {
253 |                 nodes.splice(idx, 1)
254 |                 return true
255 |             }
256 |             for (const n of nodes) {
257 |                 if (n.children && removeNode(n.children)) return true
258 |             }
259 |             return false
260 |         }
261 |         removeNode(treeData.value)
262 |     }
263 | 
264 |     const handleSaveCheck = async () => {
265 |         const rawName = saveFileName.value.trim().replace(/\.png$/i, '')
266 |         if (!rawName) return ElMessage.warning('请输入图片名称')
267 | 
268 |         const fullName = `${rawName.toLowerCase()}.png`
269 |         const isExist = imageList.value.some(img => img.name.toLowerCase() === fullName)
270 | 
271 |         if (isExist) {
272 |             try {
273 |                 await ElMessageBox.confirm(
274 |                     `当前目录下已存在同名图片 [${rawName}.png]，继续保存将覆盖原图片。是否继续？`,
275 |                     '文件覆盖警告',
276 |                     {
277 |                         confirmButtonText: '确定覆盖',
278 |                         cancelButtonText: '取消',
279 |                         type: 'warning',
280 |                         customClass: 'high-zindex-messagebox',
281 |                         appendTo: 'body'
282 |                     }
283 |                 )
284 |             } catch {
285 |                 return
286 |             }
287 |         }
288 | 
289 |         saving.value = true
290 |         emit('save', {
291 |             relativePath: currentRelPath.value,
292 |             fileName: rawName
293 |         })
294 |         setTimeout(() => { saving.value = false }, 500)
295 |     }
296 | 
297 |     const confirmSelect = () => {
298 |         if (!selectedImage.value) return ElMessage.warning('请选择一张图片')
299 |         const cleanImgName = selectedImage.value.replace(/\.png$/i, '')
300 |         const fullPath = currentRelPath.value
301 |             ? `${currentRelPath.value}/${cleanImgName}`
302 |             : cleanImgName
303 |         emit('select', fullPath)
304 |     }
305 | 
306 |     // ⚡ 增加对 initialPath 和 mode 的全量监听
307 |     watch(
308 |         () => [props.projectPath, props.initialPath, props.mode],
309 |         ([newPath, newInitPath]) => {
310 |             if (newPath) {
311 |                 selectedImage.value = ''
312 |                 saveFileName.value = ''
313 |                 currentRelPath.value = newInitPath || ''
314 |                 fetchTree()
315 |             }
316 |         },
317 |         { immediate: true }
318 |     )
319 | </script>
320 | 
321 | <style scoped>
322 |     .file-browser.dark-theme {
323 |         display: flex;
324 |         height: 480px;
325 |         background: var(--el-bg-color-page);
326 |         color: var(--el-text-color-regular);
327 |         border-radius: var(--app-radius-md, 8px);
328 |         overflow: hidden;
329 |         border: 1px solid var(--el-border-color-light);
330 |     }
331 | 
332 |     .tree-sidebar {
333 |         width: 240px;
334 |         background: var(--el-bg-color);
335 |         border-right: 1px solid var(--el-border-color-light);
336 |         display: flex;
337 |         flex-direction: column;
338 |     }
339 | 
340 |     .tree-header {
341 |         padding: 10px 12px;
342 |         font-size: 13px;
343 |         font-weight: 600;
344 |         color: var(--el-text-color-primary);
345 |         border-bottom: 1px solid var(--el-border-color-light);
346 |         display: flex;
347 |         justify-content: space-between;
348 |         align-items: center;
349 |     }
350 | 
351 |     .tree-wrapper {
352 |         flex: 1;
353 |         overflow-y: auto;
354 |         padding: 6px;
355 |     }
356 | 
357 |     :deep(.el-tree) {
358 |         background: transparent;
359 |         color: var(--el-text-color-regular);
360 |     }
361 | 
362 |     .custom-tree-node {
363 |         display: flex;
364 |         align-items: center;
365 |         justify-content: space-between;
366 |         width: 100%;
367 |         padding-right: 6px;
368 |         font-size: 12px;
369 |     }
370 | 
371 |     .inline-folder-input {
372 |         background: var(--el-fill-color-blank);
373 |         border: 1px solid var(--el-color-primary);
374 |         color: var(--el-text-color-primary);
375 |         border-radius: 4px;
376 |         padding: 1px 6px;
377 |         font-size: 12px;
378 |         width: 120px;
379 |         outline: none;
380 |     }
381 | 
382 |     .content-body {
383 |         flex: 1;
384 |         display: flex;
385 |         flex-direction: column;
386 |         background: var(--el-bg-color-page);
387 |     }
388 | 
389 |     .location-bar {
390 |         padding: 10px 16px;
391 |         font-size: 12px;
392 |         color: var(--el-text-color-secondary);
393 |         border-bottom: 1px solid var(--el-border-color-light);
394 |         background: var(--el-bg-color);
395 |     }
396 | 
397 |     .path-highlight {
398 |         color: var(--el-color-primary);
399 |         font-weight: 600;
400 |         margin-left: 4px;
401 |     }
402 | 
403 |     .image-grid {
404 |         flex: 1;
405 |         padding: 12px;
406 |         display: grid;
407 |         grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
408 |         gap: 12px;
409 |         overflow-y: auto;
410 |         align-content: start;
411 |     }
412 | 
413 |     .image-card {
414 |         border: 1px solid var(--el-border-color-light);
415 |         border-radius: var(--app-radius-sm, 6px);
416 |         padding: 6px;
417 |         background: var(--el-bg-color);
418 |         cursor: pointer;
419 |         transition: all 0.2s;
420 |         display: flex;
421 |         flex-direction: column;
422 |         align-items: center;
423 |         user-select: none;
424 |     }
425 | 
426 |         .image-card:hover {
427 |             border-color: var(--el-color-primary);
428 |             transform: translateY(-2px);
429 |         }
430 | 
431 |         .image-card.selected {
432 |             border-color: var(--el-color-primary);
433 |             background: rgba(78, 209, 156, 0.15);
434 |         }
435 | 
436 |     .img-wrapper {
437 |         width: 100%;
438 |         height: 75px;
439 |         display: flex;
440 |         align-items: center;
441 |         justify-content: center;
442 |         background: var(--el-fill-color-blank);
443 |         border-radius: 4px;
444 |         overflow: hidden;
445 |     }
446 | 
447 |         .img-wrapper img {
448 |             max-width: 100%;
449 |             max-height: 100%;
450 |             object-fit: contain;
451 |         }
452 | 
453 |     .image-name {
454 |         font-size: 11px;
455 |         color: var(--el-text-color-secondary);
456 |         margin-top: 6px;
457 |         text-align: center;
458 |         width: 100%;
459 |         white-space: nowrap;
460 |         overflow: hidden;
461 |         text-overflow: ellipsis;
462 |     }
463 | 
464 |     .empty-tip {
465 |         grid-column: 1 / -1;
466 |         color: var(--el-text-color-placeholder);
467 |         font-size: 13px;
468 |         text-align: center;
469 |         margin-top: 60px;
470 |     }
471 | 
472 |     .action-footer {
473 |         padding: 12px 16px;
474 |         background: var(--el-bg-color);
475 |         border-top: 1px solid var(--el-border-color-light);
476 |         display: flex;
477 |         justify-content: space-between;
478 |         align-items: center;
479 |     }
480 | 
481 |     .input-group {
482 |         display: flex;
483 |         align-items: center;
484 |         gap: 8px;
485 |     }
486 | 
487 |     .btn-group {
488 |         display: flex;
489 |         gap: 8px;
490 |         align-items: center;
491 |     }
492 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\PanelContainer.vue

- Extension: .vue
- Language: unknown
- Size: 3459 bytes
- Created: 2026-07-28 20:51:34
- Modified: 2026-08-08 21:51:13

### Code

```unknown
  1 | <!-- frontend/src/components/PanelContainer.vue -->
  2 | <template>
  3 |     <div class="main-layout-container">
  4 |         <div class="pane-content">
  5 |             <PanelHeader title="可视化全景流程图 (多组同屏、右键管理、跨组连线)">
  6 |                 <div class="workspace-switcher-badge" @click="openPanelSettings">
  7 |                     <span class="device-icon">💻</span>
  8 |                     <span class="workspace-label">工作面板:</span>
  9 |                     <span class="workspace-name">{{ currentWorkspaceName }}</span>
 10 |                     <span class="dropdown-arrow">▼</span>
 11 |                 </div>
 12 |             </PanelHeader>
 13 | 
 14 |             <div class="canvas-viewport-wrapper">
 15 |                 <WorkflowCanvas />
 16 |             </div>
 17 |         </div>
 18 | 
 19 |         <PanelSettingsDialog v-model:visible="dialogVisible"
 20 |                              @apply="handleApplyContext" />
 21 |     </div>
 22 | </template>
 23 | 
 24 | <script setup>
 25 |     import { ref, computed } from 'vue'
 26 |     import { useMainStore } from '@/stores'
 27 |     import { ElMessage } from 'element-plus'
 28 |     import PanelHeader from './PanelHeader.vue'
 29 |     import WorkflowCanvas from './WorkflowCanvas.vue'
 30 |     import PanelSettingsDialog from './PanelSettingsDialog.vue'
 31 | 
 32 |     const store = useMainStore()
 33 |     const dialogVisible = ref(false)
 34 | 
 35 |     const currentWorkspaceName = computed(() => {
 36 |         const ctx = store.currentContext
 37 |         if (ctx && ctx.windowTitle) {
 38 |             return ctx.windowTitle
 39 |         }
 40 |         return 'Windows 桌面'
 41 |     })
 42 | 
 43 |     const openPanelSettings = () => {
 44 |         dialogVisible.value = true
 45 |     }
 46 | 
 47 |     const handleApplyContext = async (context) => {
 48 |         try {
 49 |             await store.setCurrentContext(context)
 50 |             ElMessage.success('工作面板切换成功')
 51 |         } catch (err) {
 52 |             ElMessage.error('切换失败: ' + err.message)
 53 |         }
 54 |     }
 55 | </script>
 56 | 
 57 | <style scoped>
 58 |     .main-layout-container {
 59 |         width: 100%;
 60 |         height: 100%;
 61 |         background: var(--el-bg-color-page);
 62 |         display: flex;
 63 |         flex-direction: column;
 64 |         box-sizing: border-box;
 65 |     }
 66 | 
 67 |     .pane-content {
 68 |         display: flex;
 69 |         flex-direction: column;
 70 |         height: 100%;
 71 |         width: 100%;
 72 |         background: var(--el-bg-color);
 73 |         overflow: hidden;
 74 |         box-sizing: border-box;
 75 |     }
 76 | 
 77 |     .canvas-viewport-wrapper {
 78 |         flex: 1;
 79 |         position: relative;
 80 |         overflow: hidden;
 81 |     }
 82 | 
 83 |     .workspace-switcher-badge {
 84 |         display: flex;
 85 |         align-items: center;
 86 |         gap: 6px;
 87 |         background: rgba(25, 26, 38, 0.85);
 88 |         border: 1px solid var(--el-border-color-light);
 89 |         padding: 2px 10px;
 90 |         border-radius: 14px;
 91 |         font-size: 12px;
 92 |         cursor: pointer;
 93 |         transition: all 0.2s ease;
 94 |         user-select: none;
 95 |         height: 24px;
 96 |     }
 97 | 
 98 |         .workspace-switcher-badge:hover {
 99 |             border-color: var(--el-color-primary);
100 |             background: rgba(38, 40, 61, 0.95);
101 |         }
102 | 
103 |     .device-icon {
104 |         font-size: 12px;
105 |     }
106 | 
107 |     .workspace-label {
108 |         color: var(--el-text-color-secondary);
109 |     }
110 | 
111 |     .workspace-name {
112 |         color: var(--el-color-primary);
113 |         font-weight: 600;
114 |     }
115 | 
116 |     .dropdown-arrow {
117 |         font-size: 9px;
118 |         color: var(--el-text-color-secondary);
119 |         margin-left: 2px;
120 |     }
121 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\PanelSettingsDialog.vue

- Extension: .vue
- Language: unknown
- Size: 6306 bytes
- Created: 2026-07-29 19:11:12
- Modified: 2026-08-08 21:19:44

### Code

```unknown
  1 | <!-- frontend/src/components/PanelSettingsDialog.vue -->
  2 | <template>
  3 |     <el-dialog v-model="dialogVisible"
  4 |                title="工作面板设置"
  5 |                width="520px"
  6 |                append-to-body
  7 |                :close-on-click-modal="false"
  8 |                @close="onClose">
  9 |         <el-form :model="localContext" label-width="120px" size="small">
 10 |             <!-- 1. 工作模式选择 -->
 11 |             <el-form-item label="工作模式">
 12 |                 <el-radio-group v-model="localContext.workMode">
 13 |                     <el-radio value="window">指定窗口/模拟器</el-radio>
 14 |                     <el-radio value="desktop">全桌面模式</el-radio>
 15 |                 </el-radio-group>
 16 |             </el-form-item>
 17 | 
 18 |             <!-- 2. 指定窗口模式下的参数 -->
 19 |             <template v-if="localContext.workMode === 'window'">
 20 |                 <el-form-item label="窗口标题">
 21 |                     <el-select v-model="localContext.windowTitle"
 22 |                                filterable
 23 |                                allow-create
 24 |                                default-first-option
 25 |                                placeholder="下拉选择或手动输入窗口标题"
 26 |                                style="width: 100%;"
 27 |                                @focus="fetchWindows">
 28 |                         <el-option v-for="w in windowList"
 29 |                                    :key="w.hwnd"
 30 |                                    :label="w.title"
 31 |                                    :value="w.title" />
 32 |                     </el-select>
 33 |                     <div class="setting-tip">
 34 |                         💡 提示：已被最小化的窗口不会列出，请先还原窗口。
 35 |                     </div>
 36 |                 </el-form-item>
 37 | 
 38 |                 <el-form-item label="模拟器模式">
 39 |                     <el-switch v-model="localContext.isEmulator" />
 40 |                 </el-form-item>
 41 |             </template>
 42 | 
 43 |             <!-- 3. 通用裁剪参数 -->
 44 |             <el-form-item label="裁剪 (T,B,L,R)">
 45 |                 <div style="display: flex; gap: 6px;">
 46 |                     <el-input-number v-model="localContext.offsetTop" :min="0" controls-position="right" style="width:80px;" />
 47 |                     <el-input-number v-model="localContext.offsetBottom" :min="0" controls-position="right" style="width:80px;" />
 48 |                     <el-input-number v-model="localContext.offsetLeft" :min="0" controls-position="right" style="width:80px;" />
 49 |                     <el-input-number v-model="localContext.offsetRight" :min="0" controls-position="right" style="width:80px;" />
 50 |                 </div>
 51 |             </el-form-item>
 52 | 
 53 |             <!-- 4. 目标尺寸设置 -->
 54 |             <template v-if="localContext.workMode === 'window'">
 55 |                 <el-form-item label="目标尺寸(宽×高)">
 56 |                     <div class="dimension-box">
 57 |                         <el-input-number v-model="localContext.targetContentWidth" :min="0" placeholder="0为不修改" style="width:110px;" />
 58 |                         <span class="dimension-cross">×</span>
 59 |                         <el-input-number v-model="localContext.targetContentHeight" :min="0" placeholder="0为不修改" style="width:110px;" />
 60 |                     </div>
 61 |                     <div class="setting-tip">(设为0代表不强制调整窗口大小)</div>
 62 |                 </el-form-item>
 63 |             </template>
 64 |         </el-form>
 65 | 
 66 |         <template #footer>
 67 |             <el-button @click="dialogVisible = false">取消</el-button>
 68 |             <el-button type="primary" @click="applyContext">应用</el-button>
 69 |         </template>
 70 |     </el-dialog>
 71 | </template>
 72 | 
 73 | <script setup>
 74 |     import { ref, watch, computed } from 'vue'
 75 |     import { useMainStore } from '@/stores'
 76 |     import { workspaceApi } from '@/api/workspaceApi'
 77 | 
 78 |     const props = defineProps({
 79 |         visible: { type: Boolean, default: false }
 80 |     })
 81 | 
 82 |     const emit = defineEmits(['update:visible', 'apply'])
 83 | 
 84 |     const store = useMainStore()
 85 | 
 86 |     const localContext = ref({
 87 |         workMode: 'window',
 88 |         windowTitle: '',
 89 |         isEmulator: false,
 90 |         offsetTop: 0,
 91 |         offsetBottom: 0,
 92 |         offsetLeft: 0,
 93 |         offsetRight: 0,
 94 |         targetContentWidth: 0,
 95 |         targetContentHeight: 0
 96 |     })
 97 | 
 98 |     const windowList = ref([])
 99 | 
100 |     const dialogVisible = computed({
101 |         get: () => props.visible,
102 |         set: (val) => emit('update:visible', val)
103 |     })
104 | 
105 |     watch(() => props.visible, (val) => {
106 |         if (val) {
107 |             const ctx = store.currentContext
108 |             localContext.value = {
109 |                 workMode: ctx.workMode || (ctx.windowTitle ? 'window' : 'desktop'),
110 |                 windowTitle: ctx.windowTitle || '',
111 |                 isEmulator: ctx.isEmulator || false,
112 |                 offsetTop: ctx.offsetTop || 0,
113 |                 offsetBottom: ctx.offsetBottom || 0,
114 |                 offsetLeft: ctx.offsetLeft || 0,
115 |                 offsetRight: ctx.offsetRight || 0,
116 |                 targetContentWidth: ctx.targetContentWidth || 0,
117 |                 targetContentHeight: ctx.targetContentHeight || 0
118 |             }
119 |             fetchWindows()
120 |         }
121 |     })
122 | 
123 |     const fetchWindows = async () => {
124 |         try {
125 |             const res = await workspaceApi.getWindows()
126 |             windowList.value = res.windows || []
127 |         } catch (err) {
128 |             console.error('获取窗口列表失败', err)
129 |         }
130 |     }
131 | 
132 |     const applyContext = () => {
133 |         if (localContext.value.workMode === 'desktop') {
134 |             localContext.value.windowTitle = ''
135 |             localContext.value.isEmulator = false
136 |         }
137 |         emit('apply', localContext.value)
138 |         dialogVisible.value = false
139 |     }
140 | 
141 |     const onClose = () => {
142 |         dialogVisible.value = false
143 |     }
144 | </script>
145 | 
146 | <style scoped>
147 |     .setting-tip {
148 |         font-size: 11px;
149 |         color: var(--el-text-color-secondary);
150 |         margin-top: 4px;
151 |         line-height: 1.3;
152 |     }
153 | 
154 |     .dimension-box {
155 |         display: flex;
156 |         align-items: center;
157 |         gap: 8px;
158 |     }
159 | 
160 |     .dimension-cross {
161 |         color: var(--el-text-color-secondary);
162 |         font-weight: bold;
163 |     }
164 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\ParamRenderer.vue

- Extension: .vue
- Language: unknown
- Size: 9424 bytes
- Created: 2026-07-29 15:57:36
- Modified: 2026-08-12 12:08:44

### Code

```unknown
  1 | <!-- frontend/src/components/ParamRenderer.vue -->
  2 | <template>
  3 |     <div v-if="isVisible" class="param-renderer" :class="{ 'is-stacked': isStackedType }">
  4 |         <!-- 统一标签渲染 -->
  5 |         <div v-if="label && !isCoordType" class="param-label">
  6 |             <span>{{ displayLabel }}</span>
  7 |         </div>
  8 | 
  9 |         <!-- 动态控件分发映射 -->
 10 |         <div class="param-control">
 11 |             <component :is="activeControl"
 12 |                        :config="config"
 13 |                        :model-value="modelValue"
 14 |                        :label="displayLabel"
 15 |                        :context="context"
 16 |                        :image-version="imageVersion"
 17 |                        @update:model-value="handleUpdate"
 18 |                        @auto-change-type="handleAutoChangeType"
 19 |                        @open-browser="openBrowser"
 20 |                        @open-screenshot="openScreenshot"
 21 |                        @open-cond-dialog="handleOpenCondDialog" />
 22 |         </div>
 23 | 
 24 |         <!-- ⚡ 彻底移除 :z-index="2050" 硬编码，防止打断 Element Plus 嵌套弹窗栈 -->
 25 |         <el-dialog v-model="browserVisible"
 26 |                    :title="fileBrowserMode === 'save' ? '选择保存目录并输入图片名称' : '选择模板图片'"
 27 |                    width="80%"
 28 |                    top="5vh"
 29 |                    append-to-body
 30 |                    :close-on-click-modal="false"
 31 |                    @close="handleBrowserClose">
 32 |             <FileBrowser ref="fileBrowserRef"
 33 |                          :project-path="projectPath"
 34 |                          :mode="fileBrowserMode"
 35 |                          :initial-path="browserInitialPath"
 36 |                          @select="onFileSelected"
 37 |                          @save="onFileSave"
 38 |                          @close="browserVisible = false" />
 39 |         </el-dialog>
 40 | 
 41 |         <ScreenshotTool ref="screenshotToolRef"
 42 |                         @template-crop-selected="onTemplateCropSelected"
 43 |                         @point-selected="onPointSelected"
 44 |                         @region-selected="onRegionSelected" />
 45 | 
 46 |         <ConditionDialog v-model:visible="condDialogVisible"
 47 |                          :show-jump-config="isBranchMode"
 48 |                          :initial-data="editingCondData"
 49 |                          @open-browser="e => openBrowser('select', e)"
 50 |                          @open-screenshot="e => openScreenshot('template', e)"
 51 |                          @save="handleCondSave" />
 52 |     </div>
 53 | </template>
 54 | 
 55 | <script setup>
 56 |     import { ref, computed } from 'vue'
 57 |     import { ElMessage } from 'element-plus'
 58 |     import { useMainStore } from '@/stores'
 59 |     import { workspaceApi } from '@/api/workspaceApi'
 60 |     import { controlMap } from './controls'
 61 | 
 62 |     import VariableInputControl from './controls/VariableInputControl.vue'
 63 |     import ScreenshotTool from '@/components/ScreenshotTool.vue'
 64 |     import FileBrowser from '@/components/FileBrowser.vue'
 65 |     import ConditionDialog from '@/components/conditions/ConditionDialog.vue'
 66 | 
 67 |     const props = defineProps({
 68 |         config: { type: Object, required: true },
 69 |         value: { required: false },
 70 |         label: { type: String, default: '' },
 71 |         context: { type: Object, default: () => ({}) }
 72 |     })
 73 | 
 74 |     const emit = defineEmits(['update', 'autoChangeType'])
 75 |     const store = useMainStore()
 76 |     const projectPath = computed(() => store.currentProjectPath)
 77 | 
 78 |     const activeControl = computed(() => {
 79 |         const type = props.config.type
 80 |         if (type === 'variable' || type === 'autocomplete') {
 81 |             return VariableInputControl
 82 |         }
 83 |         return controlMap[type] || controlMap.str
 84 |     })
 85 | 
 86 |     const modelValue = computed(() => props.value)
 87 |     const isCoordType = computed(() => props.config.type && props.config.type.startsWith('list_int'))
 88 | 
 89 |     const isStackedType = computed(() => {
 90 |         return [
 91 |             'margin4', 'size2', 'file',
 92 |             'condition_list_editor', 'branch_candidate_editor',
 93 |             'condition_list', 'candidates', 'list_dict', 'textarea'
 94 |         ].includes(props.config.type)
 95 |     })
 96 | 
 97 |     const isVisible = computed(() => {
 98 |         const rule = props.config.visible_if
 99 |         if (!rule) return true
100 |         const { field, operator, value } = rule
101 |         const targetValue = props.context?.[field]
102 |         switch (operator) {
103 |             case 'eq': return targetValue === value
104 |             case 'ne': return targetValue !== value
105 |             case 'in': return Array.isArray(value) && value.includes(targetValue)
106 |             default: return true
107 |         }
108 |     })
109 | 
110 |     const displayLabel = computed(() => props.config.label || props.label || '')
111 | 
112 |     const handleUpdate = (val) => emit('update', val)
113 |     const handleAutoChangeType = (varType) => emit('autoChangeType', varType)
114 | 
115 |     const fileBrowserRef = ref(null)
116 |     const screenshotToolRef = ref(null)
117 |     const browserVisible = ref(false)
118 |     const fileBrowserMode = ref('select')
119 |     const browserInitialPath = ref('')
120 |     const pendingCropRect = ref(null)
121 |     const imageVersion = ref(Date.now())
122 | 
123 |     const condDialogVisible = ref(false)
124 |     const isBranchMode = ref(false)
125 |     const editingIdx = ref(-1)
126 |     const editingCondData = ref(null)
127 | 
128 |     const openBrowser = (mode = 'select', triggerEvent = null) => {
129 |         if (!projectPath.value) return ElMessage.warning('请先打开项目')
130 |         fileBrowserMode.value = mode
131 |         if (mode === 'select') pendingCropRect.value = null
132 | 
133 |         const isOcr = props.config?.label?.includes('OCR') || props.label?.includes('OCR')
134 |         browserInitialPath.value = isOcr ? 'ocr' : ''
135 | 
136 |         browserVisible.value = true
137 |         if (screenshotToolRef.value) screenshotToolRef.value.setPauseState(true)
138 |     }
139 | 
140 |     const handleBrowserClose = () => {
141 |         browserVisible.value = false
142 |         if (screenshotToolRef.value) screenshotToolRef.value.setPauseState(false)
143 |     }
144 | 
145 |     const openScreenshot = (mode = 'template', triggerEvent = null) => {
146 |         if (screenshotToolRef.value) {
147 |             screenshotToolRef.value.open(mode, triggerEvent)
148 |         }
149 |     }
150 | 
151 |     const onFileSelected = (relPath) => {
152 |         if (fileBrowserMode.value === 'save') return
153 |         const cleanPath = relPath.replace(/\.png$/i, '')
154 |         emit('update', cleanPath)
155 |         imageVersion.value = Date.now()
156 |         browserVisible.value = false
157 |     }
158 | 
159 |     const onTemplateCropSelected = (cropRect) => {
160 |         pendingCropRect.value = cropRect
161 |         openBrowser('save')
162 |     }
163 | 
164 |     const onFileSave = async ({ relativePath, fileName }) => {
165 |         if (!pendingCropRect.value) return ElMessage.error('缺少截图框选数据')
166 |         try {
167 |             const cleanFileName = fileName.trim().replace(/\.png$/i, '')
168 |             const cleanRelPath = relativePath ? relativePath.replace(/\.png$/i, '') : ''
169 |             const fullTemplateName = cleanRelPath ? `${cleanRelPath}/${cleanFileName}` : cleanFileName
170 | 
171 |             await workspaceApi.cropScreenshot(projectPath.value, fullTemplateName, pendingCropRect.value)
172 | 
173 |             emit('update', fullTemplateName)
174 |             imageVersion.value = Date.now()
175 |             ElMessage.success(`模板图片 [${fullTemplateName}] 保存成功`)
176 | 
177 |             browserVisible.value = false
178 |             pendingCropRect.value = null
179 |             if (screenshotToolRef.value) screenshotToolRef.value.close()
180 |         } catch (err) {
181 |             ElMessage.error('保存失败: ' + err.message)
182 |         }
183 |     }
184 | 
185 |     const onPointSelected = (pointArr) => emit('update', pointArr)
186 |     const onRegionSelected = (regionArr) => emit('update', regionArr)
187 | 
188 |     const handleOpenCondDialog = ({ idx, data, isBranch }) => {
189 |         isBranchMode.value = isBranch
190 |         editingIdx.value = idx
191 |         editingCondData.value = data
192 |         condDialogVisible.value = true
193 |     }
194 | 
195 |     const handleCondSave = ({ condition, on_success }) => {
196 |         const currentList = Array.isArray(props.value) ? [...props.value] : []
197 |         const payload = isBranchMode.value ? { condition, on_success } : condition
198 | 
199 |         if (editingIdx.value > -1) {
200 |             currentList[editingIdx.value] = payload
201 |         } else {
202 |             currentList.push(payload)
203 |         }
204 |         emit('update', currentList)
205 |     }
206 | </script>
207 | 
208 | <style scoped>
209 |     .param-renderer {
210 |         display: flex;
211 |         align-items: center;
212 |         justify-content: space-between;
213 |         gap: 12px;
214 |         margin-bottom: 12px;
215 |     }
216 | 
217 |         .param-renderer.is-stacked {
218 |             flex-direction: column;
219 |             align-items: flex-start;
220 |             gap: 6px;
221 |         }
222 | 
223 |             .param-renderer.is-stacked .param-label {
224 |                 width: 100%;
225 |                 margin-bottom: 2px;
226 |             }
227 | 
228 |             .param-renderer.is-stacked .param-control {
229 |                 justify-content: flex-start;
230 |                 width: 100%;
231 |             }
232 | 
233 |     .param-label {
234 |         font-size: 13px;
235 |         color: var(--el-text-color-primary);
236 |         font-weight: 500;
237 |         white-space: nowrap;
238 |         flex-shrink: 0;
239 |         width: 120px;
240 |         text-align: left;
241 |     }
242 | 
243 |     .param-control {
244 |         flex: 1;
245 |         display: flex;
246 |         justify-content: flex-end;
247 |         align-items: center;
248 |         width: 100%;
249 |     }
250 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\ScreenshotTool.vue

- Extension: .vue
- Language: unknown
- Size: 17856 bytes
- Created: 2026-07-29 10:53:40
- Modified: 2026-08-12 12:09:18

### Code

```unknown
  1 | <!-- frontend/src/components/ScreenshotTool.vue -->
  2 | <template>
  3 |     <teleport to="body">
  4 |         <div v-if="visible"
  5 |              ref="overlayRef"
  6 |              class="screenshot-overlay"
  7 |              :style="{ zIndex: overlayZIndex }"
  8 |              tabindex="0"
  9 |              @click.self="close"
 10 |              @keydown.stop="handleKeyDown">
 11 |             <div class="main-layout" @click.stop>
 12 |                 <!-- 左侧：工作区 Canvas 画面 -->
 13 |                 <div ref="containerRef" class="canvas-wrapper">
 14 |                     <canvas ref="canvasRef"
 15 |                             @mousedown="onMouseDown"
 16 |                             @mousemove="onMouseMove"
 17 |                             @mouseup="onMouseUp" />
 18 |                 </div>
 19 | 
 20 |                 <!-- 右侧：微调与放大预览面板 -->
 21 |                 <div class="sidebar-panel">
 22 |                     <div class="panel-header">
 23 |                         <span v-if="mode === 'template'">📷 模板截图录入</span>
 24 |                         <span v-else-if="mode === 'point'">📍 坐标点提取</span>
 25 |                         <span v-else-if="mode === 'region'">📐 区域框选</span>
 26 |                     </div>
 27 | 
 28 |                     <!-- 选点模式预览 -->
 29 |                     <div v-if="mode === 'point'" class="panel-section">
 30 |                         <div class="section-title">标定点局域放大</div>
 31 |                         <div class="preview-box">
 32 |                             <canvas ref="pointCanvasRef" width="160" height="160" />
 33 |                         </div>
 34 |                         <div class="data-group">
 35 |                             <div class="data-item">
 36 |                                 <span class="label">工作区相对坐标:</span>
 37 |                                 <span class="value">{{ point ? `${point.x}, ${point.y}` : '未点击选点' }}</span>
 38 |                             </div>
 39 |                         </div>
 40 |                         <div class="tips-box">
 41 |                             <p>💡 点击左侧画板标定坐标点</p>
 42 |                             <p>💡 <b>方向键 (↑↓←→)</b> 微调像素点位</p>
 43 |                             <p>💡 <b>回车 (Enter)</b> 确认并填入</p>
 44 |                         </div>
 45 |                     </div>
 46 | 
 47 |                     <!-- 选区 / 模板模式预览 -->
 48 |                     <div v-else class="panel-section">
 49 |                         <div class="section-title">选区高精放大预览</div>
 50 |                         <div class="preview-box">
 51 |                             <canvas ref="regionCanvasRef" width="220" height="150" />
 52 |                         </div>
 53 |                         <div class="data-group">
 54 |                             <div class="data-item">
 55 |                                 <span class="label">起点 (X, Y):</span>
 56 |                                 <span class="value">{{ selection ? `${selection.x}, ${selection.y}` : '0, 0' }}</span>
 57 |                             </div>
 58 |                             <div class="data-item">
 59 |                                 <span class="label">尺寸 (W × H):</span>
 60 |                                 <span class="value highlight">{{ selection ? `${selection.w} × ${selection.h}` : '0 × 0' }}</span>
 61 |                             </div>
 62 |                         </div>
 63 |                         <div class="tips-box">
 64 |                             <p>💡 拖拽鼠标划定框选范围</p>
 65 |                             <p>💡 <b>方向键 (↑↓←→)</b> 平移位置</p>
 66 |                             <p>💡 <b>Shift + 方向键</b> 调整宽高</p>
 67 |                             <p>💡 <b>回车 (Enter)</b> 确认并进入保存</p>
 68 |                         </div>
 69 |                     </div>
 70 | 
 71 |                     <div class="panel-footer">
 72 |                         <el-button type="success" style="width: 100%; margin-bottom: 8px;" @click="confirmSelection">
 73 |                             确认选择 (Enter)
 74 |                         </el-button>
 75 |                         <el-button type="info" style="width: 100%; margin-left: 0;" @click="close">
 76 |                             取消 (Esc)
 77 |                         </el-button>
 78 |                     </div>
 79 |                 </div>
 80 |             </div>
 81 |         </div>
 82 |     </teleport>
 83 | </template>
 84 | 
 85 | <script setup>
 86 |     import { ref, reactive, nextTick } from 'vue'
 87 |     import { ElMessage } from 'element-plus'
 88 |     import { useMainStore } from '@/stores'
 89 |     import { workspaceApi } from '@/api/workspaceApi'
 90 |     import { getNextZIndex } from '@/utils/zIndexManager'
 91 | 
 92 |     const emit = defineEmits(['template-crop-selected', 'point-selected', 'region-selected'])
 93 |     const store = useMainStore()
 94 | 
 95 |     const visible = ref(false)
 96 |     const mode = ref('template')
 97 |     const isPausedForDialog = ref(false)
 98 |     const overlayZIndex = ref(3000)
 99 | 
100 |     const canvasRef = ref(null)
101 |     const containerRef = ref(null)
102 |     const pointCanvasRef = ref(null)
103 |     const regionCanvasRef = ref(null)
104 |     const overlayRef = ref(null)
105 | 
106 |     let imgObj = null
107 |     let isDrawing = false
108 |     let startImgPoint = { x: 0, y: 0 }
109 | 
110 |     const drawScale = reactive({ scale: 1, offsetX: 0, offsetY: 0, imgW: 0, imgH: 0 })
111 |     const selection = ref(null)
112 |     const point = ref(null)
113 | 
114 |     const open = async (targetMode = 'template', triggerSource = null) => {
115 |         mode.value = targetMode
116 |         selection.value = null
117 |         point.value = null
118 |         isPausedForDialog.value = false
119 | 
120 |         // ⚡ 动态提升 Z-Index，确保绝对压盖在触发源的顶层
121 |         overlayZIndex.value = getNextZIndex(triggerSource)
122 | 
123 |         try {
124 |             const res = await workspaceApi.getFullScreenshot(store.currentProjectPath)
125 |             if (!res || !res.image) {
126 |                 return ElMessage.error('获取工作区截图失败')
127 |             }
128 | 
129 |             visible.value = true
130 |             await nextTick()
131 | 
132 |             if (overlayRef.value) overlayRef.value.focus()
133 | 
134 |             imgObj = new Image()
135 |             imgObj.src = 'data:image/png;base64,' + res.image
136 |             imgObj.onload = () => {
137 |                 initAspectCanvas(res.width, res.height)
138 |             }
139 |         } catch (err) {
140 |             ElMessage.error('调出截图工具失败: ' + err.message)
141 |         }
142 |     }
143 | 
144 |     const setPauseState = (paused) => {
145 |         isPausedForDialog.value = paused
146 |     }
147 | 
148 |     const initAspectCanvas = (rawW, rawH) => {
149 |         const canvas = canvasRef.value
150 |         if (!canvas || !containerRef.value) return
151 | 
152 |         const screenW = containerRef.value.clientWidth
153 |         const screenH = containerRef.value.clientHeight
154 | 
155 |         canvas.width = screenW
156 |         canvas.height = screenH
157 | 
158 |         const scaleW = screenW / rawW
159 |         const scaleH = screenH / rawH
160 |         const scale = Math.min(scaleW, scaleH, 1)
161 | 
162 |         const drawW = rawW * scale
163 |         const drawH = rawH * scale
164 |         const offsetX = (screenW - drawW) / 2
165 |         const offsetY = (screenH - drawH) / 2
166 | 
167 |         drawScale.scale = scale
168 |         drawScale.offsetX = offsetX
169 |         drawScale.offsetY = offsetY
170 |         drawScale.imgW = rawW
171 |         drawScale.imgH = rawH
172 | 
173 |         redrawCanvas()
174 |     }
175 | 
176 |     const screenToImgPos = (clientX, clientY) => {
177 |         const rect = containerRef.value.getBoundingClientRect()
178 |         const xInCanvas = clientX - rect.left
179 |         const yInCanvas = clientY - rect.top
180 | 
181 |         const ix = Math.round((xInCanvas - drawScale.offsetX) / drawScale.scale)
182 |         const iy = Math.round((yInCanvas - drawScale.offsetY) / drawScale.scale)
183 |         const clampedX = Math.max(0, Math.min(drawScale.imgW, ix))
184 |         const clampedY = Math.max(0, Math.min(drawScale.imgH, iy))
185 |         return { x: clampedX, y: clampedY }
186 |     }
187 | 
188 |     const imgToCanvasPos = (imgX, imgY) => {
189 |         const cx = imgX * drawScale.scale + drawScale.offsetX
190 |         const cy = imgY * drawScale.scale + drawScale.offsetY
191 |         return { x: cx, y: cy }
192 |     }
193 | 
194 |     const redrawCanvas = () => {
195 |         const canvas = canvasRef.value
196 |         if (!canvas || !imgObj) return
197 |         const ctx = canvas.getContext('2d')
198 | 
199 |         ctx.clearRect(0, 0, canvas.width, canvas.height)
200 |         ctx.fillStyle = 'rgba(15, 15, 25, 0.95)'
201 |         ctx.fillRect(0, 0, canvas.width, canvas.height)
202 | 
203 |         const { offsetX, offsetY, imgW, imgH, scale } = drawScale
204 |         const drawW = imgW * scale
205 |         const drawH = imgH * scale
206 | 
207 |         ctx.drawImage(imgObj, offsetX, offsetY, drawW, drawH)
208 | 
209 |         ctx.strokeStyle = '#409eff'
210 |         ctx.lineWidth = 1.5
211 |         ctx.strokeRect(offsetX, offsetY, drawW, drawH)
212 | 
213 |         if (selection.value && (mode.value === 'template' || mode.value === 'region')) {
214 |             const { x, y, w, h } = selection.value
215 |             const p1 = imgToCanvasPos(x, y)
216 |             const p2 = imgToCanvasPos(x + w, y + h)
217 |             const cw = p2.x - p1.x
218 |             const ch = p2.y - p1.y
219 | 
220 |             if (w > 0 && h > 0) {
221 |                 ctx.drawImage(imgObj, x, y, w, h, p1.x, p1.y, cw, ch)
222 |                 ctx.strokeStyle = '#67C23A'
223 |                 ctx.lineWidth = 2
224 |                 ctx.strokeRect(p1.x, p1.y, cw, ch)
225 |             }
226 |         }
227 | 
228 |         if (point.value && mode.value === 'point') {
229 |             const cp = imgToCanvasPos(point.value.x, point.value.y)
230 |             ctx.beginPath()
231 |             ctx.arc(cp.x, cp.y, 6, 0, Math.PI * 2)
232 |             ctx.fillStyle = '#FF4D4F'
233 |             ctx.fill()
234 |             ctx.strokeStyle = '#FFFFFF'
235 |             ctx.lineWidth = 2
236 |             ctx.stroke()
237 | 
238 |             ctx.beginPath()
239 |             ctx.moveTo(cp.x - 12, cp.y); ctx.lineTo(cp.x + 12, cp.y)
240 |             ctx.moveTo(cp.x, cp.y - 12); ctx.lineTo(cp.x, cp.y + 12)
241 |             ctx.strokeStyle = '#FF4D4F'
242 |             ctx.lineWidth = 1.5
243 |             ctx.stroke()
244 |         }
245 | 
246 |         updateSidebarPreviews()
247 |     }
248 | 
249 |     const updateSidebarPreviews = () => {
250 |         if (mode.value === 'point' && point.value) {
251 |             nextTick(() => {
252 |                 const pCanvas = pointCanvasRef.value
253 |                 if (!pCanvas || !imgObj) return
254 |                 const pCtx = pCanvas.getContext('2d')
255 |                 pCtx.clearRect(0, 0, 160, 160)
256 |                 pCtx.drawImage(imgObj, point.value.x - 20, point.value.y - 20, 40, 40, 0, 0, 160, 160)
257 |                 pCtx.strokeStyle = '#FF4D4F'
258 |                 pCtx.lineWidth = 1
259 |                 pCtx.beginPath()
260 |                 pCtx.moveTo(80, 0); pCtx.lineTo(80, 160)
261 |                 pCtx.moveTo(0, 80); pCtx.lineTo(160, 80)
262 |                 pCtx.stroke()
263 |             })
264 |         }
265 | 
266 |         if ((mode.value === 'region' || mode.value === 'template') && selection.value) {
267 |             const { x, y, w, h } = selection.value
268 |             if (w <= 0 || h <= 0) return
269 |             nextTick(() => {
270 |                 const rCanvas = regionCanvasRef.value
271 |                 if (!rCanvas || !imgObj) return
272 |                 const rCtx = rCanvas.getContext('2d')
273 |                 rCtx.clearRect(0, 0, rCanvas.width, rCanvas.height)
274 |                 rCtx.fillStyle = '#0f0f19'
275 |                 rCtx.fillRect(0, 0, rCanvas.width, rCanvas.height)
276 | 
277 |                 const pScale = Math.min(220 / w, 150 / h)
278 |                 const pw = w * pScale
279 |                 const ph = h * pScale
280 |                 const px = (220 - pw) / 2
281 |                 const py = (150 - ph) / 2
282 | 
283 |                 rCtx.drawImage(imgObj, x, y, w, h, px, py, pw, ph)
284 |                 rCtx.strokeStyle = '#67C23A'
285 |                 rCtx.lineWidth = 1.5
286 |                 rCtx.strokeRect(px, py, pw, ph)
287 |             })
288 |         }
289 |     }
290 | 
291 |     const onMouseDown = (e) => {
292 |         if (isPausedForDialog.value) return
293 |         isDrawing = true
294 |         const imgPos = screenToImgPos(e.clientX, e.clientY)
295 |         startImgPoint = imgPos
296 | 
297 |         if (mode.value === 'point') {
298 |             point.value = { ...imgPos }
299 |             redrawCanvas()
300 |         } else {
301 |             selection.value = { x: imgPos.x, y: imgPos.y, w: 0, h: 0 }
302 |         }
303 |     }
304 | 
305 |     const onMouseMove = (e) => {
306 |         if (isPausedForDialog.value || !isDrawing) return
307 |         const imgPos = screenToImgPos(e.clientX, e.clientY)
308 | 
309 |         if (mode.value === 'point') {
310 |             point.value = { ...imgPos }
311 |         } else {
312 |             const x = Math.min(startImgPoint.x, imgPos.x)
313 |             const y = Math.min(startImgPoint.y, imgPos.y)
314 |             const w = Math.abs(imgPos.x - startImgPoint.x)
315 |             const h = Math.abs(imgPos.y - startImgPoint.y)
316 |             selection.value = { x, y, w, h }
317 |         }
318 |         redrawCanvas()
319 |     }
320 | 
321 |     const onMouseUp = () => {
322 |         isDrawing = false
323 |     }
324 | 
325 |     const handleKeyDown = (e) => {
326 |         if (isPausedForDialog.value) return
327 | 
328 |         if (e.key === 'Escape') return close()
329 |         if (e.key === 'Enter') return confirmSelection()
330 | 
331 |         if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
332 |             e.preventDefault()
333 |             const dx = e.key === 'ArrowLeft' ? -1 : e.key === 'ArrowRight' ? 1 : 0
334 |             const dy = e.key === 'ArrowUp' ? -1 : e.key === 'ArrowDown' ? 1 : 0
335 | 
336 |             if (mode.value === 'point' && point.value) {
337 |                 point.value.x = Math.max(0, Math.min(drawScale.imgW, point.value.x + dx))
338 |                 point.value.y = Math.max(0, Math.min(drawScale.imgH, point.value.y + dy))
339 |                 redrawCanvas()
340 |             } else if (selection.value) {
341 |                 if (e.shiftKey) {
342 |                     selection.value.w = Math.max(1, selection.value.w + dx)
343 |                     selection.value.h = Math.max(1, selection.value.h + dy)
344 |                 } else {
345 |                     selection.value.x = Math.max(0, Math.min(drawScale.imgW - selection.value.w, selection.value.x + dx))
346 |                     selection.value.y = Math.max(0, Math.min(drawScale.imgH - selection.value.h, selection.value.y + dy))
347 |                 }
348 |                 redrawCanvas()
349 |             }
350 |         }
351 |     }
352 | 
353 |     const confirmSelection = () => {
354 |         if (mode.value === 'point') {
355 |             if (!point.value) return ElMessage.warning('请先点击工作区选点')
356 |             emit('point-selected', [point.value.x, point.value.y])
357 |             close()
358 |             return
359 |         }
360 | 
361 |         if (mode.value === 'region') {
362 |             if (!selection.value || selection.value.w === 0) return ElMessage.warning('请先划定框选区域')
363 |             emit('region-selected', [selection.value.x, selection.value.y, selection.value.w, selection.value.h])
364 |             close()
365 |             return
366 |         }
367 | 
368 |         if (mode.value === 'template') {
369 |             if (!selection.value || selection.value.w === 0) return ElMessage.warning('请先划定截取区域')
370 |             emit('template-crop-selected', [selection.value.x, selection.value.y, selection.value.w, selection.value.h])
371 |             close()
372 |         }
373 |     }
374 | 
375 |     const close = () => {
376 |         visible.value = false
377 |         isPausedForDialog.value = false
378 |     }
379 | 
380 |     defineExpose({ open, close, setPauseState })
381 | </script>
382 | 
383 | <style scoped>
384 |     .screenshot-overlay {
385 |         position: fixed;
386 |         top: 0;
387 |         left: 0;
388 |         right: 0;
389 |         bottom: 0;
390 |         outline: none;
391 |         background: rgba(15, 16, 26, 0.85);
392 |         display: flex;
393 |         justify-content: center;
394 |         align-items: center;
395 |     }
396 | 
397 |     .main-layout {
398 |         display: flex;
399 |         width: 100vw;
400 |         height: 100vh;
401 |         background: var(--el-bg-color-page);
402 |     }
403 | 
404 |     .canvas-wrapper {
405 |         flex: 1;
406 |         height: 100%;
407 |         position: relative;
408 |         overflow: hidden;
409 |         cursor: crosshair;
410 |     }
411 | 
412 |     .sidebar-panel {
413 |         width: 280px;
414 |         height: 100%;
415 |         background: var(--el-bg-color);
416 |         border-left: 1px solid var(--el-border-color-light);
417 |         display: flex;
418 |         flex-direction: column;
419 |         padding: 16px;
420 |         box-shadow: -4px 0 16px rgba(0, 0, 0, 0.4);
421 |     }
422 | 
423 |     .panel-header {
424 |         font-size: 16px;
425 |         font-weight: 600;
426 |         color: var(--el-color-primary);
427 |         padding-bottom: 12px;
428 |         border-bottom: 1px solid var(--el-border-color-light);
429 |         margin-bottom: 16px;
430 |     }
431 | 
432 |     .panel-section {
433 |         flex: 1;
434 |         display: flex;
435 |         flex-direction: column;
436 |         gap: 12px;
437 |     }
438 | 
439 |     .section-title {
440 |         font-size: 13px;
441 |         color: var(--el-text-color-secondary);
442 |         font-weight: 500;
443 |     }
444 | 
445 |     .preview-box {
446 |         background: var(--el-fill-color-blank);
447 |         border: 1px dashed var(--el-border-color-light);
448 |         border-radius: var(--app-radius-sm, 6px);
449 |         padding: 8px;
450 |         display: flex;
451 |         justify-content: center;
452 |         align-items: center;
453 |     }
454 | 
455 |     .data-group {
456 |         display: flex;
457 |         flex-direction: column;
458 |         gap: 6px;
459 |         background: var(--el-fill-color-blank);
460 |         padding: 10px;
461 |         border-radius: var(--app-radius-sm, 6px);
462 |     }
463 | 
464 |     .data-item {
465 |         display: flex;
466 |         justify-content: space-between;
467 |         font-size: 12px;
468 |         color: var(--el-text-color-regular);
469 |     }
470 | 
471 |     .highlight {
472 |         color: var(--el-color-primary);
473 |         font-weight: 600;
474 |     }
475 | 
476 |     .tips-box {
477 |         background: rgba(78, 209, 156, 0.08);
478 |         border-left: 3px solid var(--el-color-primary);
479 |         padding: 8px 10px;
480 |         border-radius: 0 4px 4px 0;
481 |         font-size: 11px;
482 |         color: var(--el-text-color-secondary);
483 |         line-height: 1.6;
484 |     }
485 | 
486 |     .panel-footer {
487 |         padding-top: 12px;
488 |         border-top: 1px solid var(--el-border-color-light);
489 |     }
490 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\TaskGroupNode.vue

- Extension: .vue
- Language: unknown
- Size: 10483 bytes
- Created: 2026-08-03 20:12:17
- Modified: 2026-08-08 21:45:18

### Code

```unknown
  1 | ﻿<!-- frontend/src/components/TaskGroupNode.vue -->
  2 | <template>
  3 |     <div class="task-group-card app-card-dark"
  4 |          :class="{ 'is-current': isCurrentTask }"
  5 |          :style="{ transform: `translate(${position.x}px, ${position.y}px)` }"
  6 |          @mousedown="onCardMouseDown"
  7 |          @contextmenu.prevent.stop="onCardContextMenu">
  8 |         <!-- 卡片头部标题 -->
  9 |         <div class="task-card-header">
 10 |             <div class="task-title-area">
 11 |                 <span class="task-badge">Group</span>
 12 |                 <span class="task-name">{{ task.task_name || task.task_id }}</span>
 13 |             </div>
 14 |             <div class="task-header-btns">
 15 |                 <el-button link size="small" type="primary" title="添加节点" @click.stop="$emit('addNode', task.task_id)">
 16 |                     ➕
 17 |                 </el-button>
 18 |                 <el-button link size="small" type="danger" title="删除任务组" @click.stop="$emit('deleteTask', task.task_id)">
 19 |                     🗑️
 20 |                 </el-button>
 21 |             </div>
 22 |         </div>
 23 | 
 24 |         <!-- 节点列表区 -->
 25 |         <div class="node-list">
 26 |             <div v-for="(node, index) in (task.nodes || [])"
 27 |                  :key="node.node_id"
 28 |                  :id="`node-${node.node_id}`"
 29 |                  class="node-card-item"
 30 |                  :class="{
 31 |           'is-selected': selectedNodeId === node.node_id,
 32 |           'is-disabled': !node.enabled
 33 |         }"
 34 |                  @click.stop="$emit('selectNode', node.node_id)"
 35 |                  @contextmenu.prevent.stop="$emit('nodeContextMenu', { event: $event, task, node })">
 36 |                 <!-- 1. 节点 Card Header -->
 37 |                 <div class="node-item-header">
 38 |                     <div class="node-header-left">
 39 |                         <component :is="getNodeIcon(node.node_type)" class="node-type-icon" />
 40 |                         <span class="node-title">{{ node.node_name || node.node_id }}</span>
 41 |                     </div>
 42 |                     <span class="node-index-badge">#{{ index + 1 }}</span>
 43 |                 </div>
 44 | 
 45 |                 <!-- 2. 中间缩略图预览（适用于 image_recognition 节点） -->
 46 |                 <div v-if="node.node_type === 'image_recognition'" class="node-body-image">
 47 |                     <div v-if="node.params?.image_source"
 48 |                          class="image-thumb-box"
 49 |                          :style="{ '--bg-url': `url(${getImageUrl(node.params.image_source)})` }">
 50 |                         <img :src="getImageUrl(node.params.image_source)"
 51 |                              class="thumb-img"
 52 |                              alt="模板缩略图"
 53 |                              @error="e => { e.target.style.display = 'none' }" />
 54 |                     </div>
 55 |                     <div v-else class="empty-thumb-box">
 56 |                         <span>未选模板图片</span>
 57 |                     </div>
 58 |                 </div>
 59 | 
 60 |                 <!-- 3. 卡片底部 Tag 区域 -->
 61 |                 <div class="node-item-footer">
 62 |                     <span class="footer-tag">延时: {{ node.delay_before ?? 0 }}ms</span>
 63 |                     <span class="footer-tag">循环: {{ node.loop_count ?? 1 }}次</span>
 64 |                 </div>
 65 | 
 66 |                 <!-- 4. 连线锚点 -->
 67 |                 <div class="anchor anchor-in" :data-node-id="node.node_id" data-anchor-type="in" />
 68 |                 <div class="anchor anchor-out" :data-node-id="node.node_id" data-anchor-type="out" />
 69 |             </div>
 70 | 
 71 |             <div v-if="!task.nodes || !task.nodes.length" class="empty-node-tip">
 72 |                 点击右上角 ➕ 添加节点
 73 |             </div>
 74 |         </div>
 75 |     </div>
 76 | </template>
 77 | 
 78 | <script setup>
 79 |     import { computed } from 'vue'
 80 |     import { useMainStore } from '@/stores'
 81 |     import {
 82 |         MousePointerClick, Clock, Target, FileSearch, GitBranch,
 83 |         SearchCheck, Binary, FileCode, Image
 84 |     } from 'lucide-vue-next'
 85 | 
 86 |     const props = defineProps({
 87 |         task: { type: Object, required: true },
 88 |         currentTaskId: { type: String, default: null },
 89 |         selectedNodeId: { type: String, default: null },
 90 |         position: { type: Object, default: () => ({ x: 100, y: 100 }) }
 91 |     })
 92 | 
 93 |     const emit = defineEmits([
 94 |         'selectNode',
 95 |         'addNode',
 96 |         'deleteTask',
 97 |         'cardMouseDown',
 98 |         'cardContextMenu',
 99 |         'nodeContextMenu'
100 |     ])
101 | 
102 |     const store = useMainStore()
103 | 
104 |     const isCurrentTask = computed(() => props.currentTaskId === props.task.task_id)
105 | 
106 |     const getNodeIcon = (type) => {
107 |         const iconMap = {
108 |             click: MousePointerClick,
109 |             wait: Clock,
110 |             set_window: Target,
111 |             image_recognition: FileSearch,
112 |             branch: GitBranch,
113 |             logic_check: SearchCheck,
114 |             ocr_recognition: Binary,
115 |             script_call: FileCode
116 |         }
117 |         return iconMap[type] || Target
118 |     }
119 | 
120 |     const getImageUrl = (name) => {
121 |         if (!name) return ''
122 |         let cleanName = name.replace(/\\/g, '/')
123 |         if (!/\.(png|jpg|jpeg)$/i.test(cleanName)) cleanName += '.png'
124 |         return `/api/image/thumb?project_path=${encodeURIComponent(store.currentProjectPath || '')}&name=${encodeURIComponent(cleanName)}`
125 |     }
126 | 
127 |     const onCardMouseDown = (e) => {
128 |         emit('cardMouseDown', { event: e, taskId: props.task.task_id })
129 |     }
130 | 
131 |     const onCardContextMenu = (e) => {
132 |         emit('cardContextMenu', { event: e, task: props.task })
133 |     }
134 | </script>
135 | 
136 | <style scoped>
137 |     .task-group-card {
138 |         position: absolute;
139 |         width: 280px;
140 |         background: var(--el-bg-color);
141 |         border: 1px solid var(--el-border-color-light);
142 |         border-radius: var(--app-radius-md, 8px);
143 |         box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
144 |         user-select: none;
145 |         cursor: move;
146 |         z-index: 10;
147 |         transition: border-color 0.2s, box-shadow 0.2s;
148 |     }
149 | 
150 |         .task-group-card.is-current {
151 |             border-color: var(--el-color-primary);
152 |             box-shadow: 0 0 12px rgba(78, 209, 156, 0.25);
153 |         }
154 | 
155 |     .task-card-header {
156 |         display: flex;
157 |         align-items: center;
158 |         justify-content: space-between;
159 |         padding: 10px 12px;
160 |         background: var(--el-fill-color-blank);
161 |         border-bottom: 1px solid var(--el-border-color-light);
162 |         border-radius: var(--app-radius-md, 8px) var(--app-radius-md, 8px) 0 0;
163 |     }
164 | 
165 |     .task-title-area {
166 |         display: flex;
167 |         align-items: center;
168 |         gap: 8px;
169 |     }
170 | 
171 |     .task-badge {
172 |         font-size: 10px;
173 |         background: var(--el-color-primary);
174 |         color: #122118;
175 |         padding: 1px 6px;
176 |         border-radius: 4px;
177 |         font-weight: 700;
178 |     }
179 | 
180 |     .task-name {
181 |         font-size: 13px;
182 |         font-weight: 600;
183 |         color: var(--el-text-color-primary);
184 |     }
185 | 
186 |     .node-list {
187 |         padding: 8px;
188 |         display: flex;
189 |         flex-direction: column;
190 |         gap: 8px;
191 |         min-height: 80px;
192 |     }
193 | 
194 |     .empty-node-tip {
195 |         font-size: 11px;
196 |         color: var(--el-text-color-placeholder);
197 |         text-align: center;
198 |         padding: 20px 0;
199 |     }
200 | 
201 |     .node-card-item {
202 |         position: relative;
203 |         display: flex;
204 |         flex-direction: column;
205 |         background: var(--el-fill-color-blank);
206 |         border: 1px solid var(--el-border-color-light);
207 |         border-radius: var(--app-radius-sm, 6px);
208 |         padding: 8px;
209 |         cursor: pointer;
210 |         transition: all 0.2s;
211 |     }
212 | 
213 |         .node-card-item:hover {
214 |             border-color: var(--el-color-primary);
215 |         }
216 | 
217 |         .node-card-item.is-selected {
218 |             border-color: var(--el-color-primary);
219 |             background: rgba(78, 209, 156, 0.12);
220 |         }
221 | 
222 |         .node-card-item.is-disabled {
223 |             opacity: 0.5;
224 |             filter: grayscale(1);
225 |         }
226 | 
227 |     .node-item-header {
228 |         display: flex;
229 |         align-items: center;
230 |         justify-content: space-between;
231 |     }
232 | 
233 |     .node-header-left {
234 |         display: flex;
235 |         align-items: center;
236 |         gap: 6px;
237 |         overflow: hidden;
238 |     }
239 | 
240 |     .node-type-icon {
241 |         width: 14px;
242 |         height: 14px;
243 |         color: var(--el-color-primary);
244 |         flex-shrink: 0;
245 |     }
246 | 
247 |     .node-title {
248 |         font-size: 12px;
249 |         font-weight: 600;
250 |         color: var(--el-text-color-primary);
251 |         white-space: nowrap;
252 |         overflow: hidden;
253 |         text-overflow: ellipsis;
254 |     }
255 | 
256 |     .node-index-badge {
257 |         font-size: 10px;
258 |         color: var(--el-text-color-secondary);
259 |     }
260 | 
261 |     .node-body-image {
262 |         margin-top: 6px;
263 |         height: 60px;
264 |         border-radius: 4px;
265 |         overflow: hidden;
266 |         background: #12131f;
267 |         border: 1px solid var(--el-border-color-light);
268 |     }
269 | 
270 |     .image-thumb-box {
271 |         position: relative;
272 |         width: 100%;
273 |         height: 100%;
274 |         display: flex;
275 |         align-items: center;
276 |         justify-content: center;
277 |     }
278 | 
279 |         .image-thumb-box::before {
280 |             content: '';
281 |             position: absolute;
282 |             inset: -10px;
283 |             background-image: var(--bg-url);
284 |             background-size: cover;
285 |             filter: blur(10px) brightness(0.4);
286 |         }
287 | 
288 |     .thumb-img {
289 |         position: relative;
290 |         max-width: 100%;
291 |         max-height: 100%;
292 |         object-fit: contain;
293 |         z-index: 2;
294 |     }
295 | 
296 |     .empty-thumb-box {
297 |         height: 100%;
298 |         display: flex;
299 |         align-items: center;
300 |         justify-content: center;
301 |         font-size: 10px;
302 |         color: var(--el-text-color-placeholder);
303 |     }
304 | 
305 |     .node-item-footer {
306 |         display: flex;
307 |         align-items: center;
308 |         gap: 8px;
309 |         margin-top: 6px;
310 |         font-size: 10px;
311 |         color: var(--el-text-color-secondary);
312 |     }
313 | 
314 |     .anchor {
315 |         position: absolute;
316 |         top: 50%;
317 |         width: 10px;
318 |         height: 10px;
319 |         border-radius: 50%;
320 |         background: var(--el-color-primary);
321 |         transform: translateY(-50%);
322 |         opacity: 0;
323 |         transition: opacity 0.2s;
324 |         z-index: 5;
325 |     }
326 | 
327 |     .node-card-item:hover .anchor {
328 |         opacity: 1;
329 |     }
330 | 
331 |     .anchor-in {
332 |         left: -5px;
333 |     }
334 | 
335 |     .anchor-out {
336 |         right: -5px;
337 |     }
338 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\WorkflowCanvas.vue

- Extension: .vue
- Language: unknown
- Size: 102710 bytes
- Created: 2026-08-03 17:53:47
- Modified: 2026-08-12 12:11:52

### Code

```unknown
   1 | ﻿<!-- frontend/src/components/WorkflowCanvas.vue -->
   2 | <template>
   3 |     <div ref="containerRef"
   4 |          class="custom-canvas-container"
   5 |          @mousedown="onCanvasMouseDown"
   6 |          @wheel="onCanvasWheel"
   7 |          @contextmenu="onContextMenu">
   8 |         <!-- 视口变换层 -->
   9 |         <div class="canvas-viewport" :style="viewportStyle">
  10 | 
  11 |             <!-- SVG 连线层 -->
  12 |             <svg class="canvas-edges-layer">
  13 |                 <defs>
  14 |                     <pattern id="grid-pattern" width="20" height="20" patternUnits="userSpaceOnUse">
  15 |                         <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255, 255, 255, 0.08)" stroke-width="1" />
  16 |                     </pattern>
  17 | 
  18 |                     <marker id="arrow-succ-down" viewBox="0 0 10 10" refX="5" refY="8" markerWidth="6" markerHeight="6" orient="0">
  19 |                         <path d="M 2 2 L 8 2 L 5 9 z" fill="#4ed19c" />
  20 |                     </marker>
  21 |                     <marker id="arrow-succ-up" viewBox="0 0 10 10" refX="5" refY="2" markerWidth="6" markerHeight="6" orient="0">
  22 |                         <path d="M 2 8 L 8 8 L 5 1 z" fill="#4ed19c" />
  23 |                     </marker>
  24 |                     <marker id="arrow-succ-right" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="0">
  25 |                         <path d="M 2 2 L 2 8 L 9 5 z" fill="#4ed19c" />
  26 |                     </marker>
  27 |                     <marker id="arrow-succ-left" viewBox="0 0 10 10" refX="2" refY="5" markerWidth="6" markerHeight="6" orient="0">
  28 |                         <path d="M 8 2 L 8 8 L 1 5 z" fill="#4ed19c" />
  29 |                     </marker>
  30 | 
  31 |                     <marker id="arrow-fail-down" viewBox="0 0 10 10" refX="5" refY="8" markerWidth="6" markerHeight="6" orient="0">
  32 |                         <path d="M 2 2 L 8 2 L 5 9 z" fill="#f56c6c" />
  33 |                     </marker>
  34 |                     <marker id="arrow-fail-up" viewBox="0 0 10 10" refX="5" refY="2" markerWidth="6" markerHeight="6" orient="0">
  35 |                         <path d="M 2 8 L 8 8 L 5 1 z" fill="#f56c6c" />
  36 |                     </marker>
  37 |                     <marker id="arrow-fail-right" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="0">
  38 |                         <path d="M 2 2 L 2 8 L 9 5 z" fill="#f56c6c" />
  39 |                     </marker>
  40 |                     <marker id="arrow-fail-left" viewBox="0 0 10 10" refX="2" refY="5" markerWidth="6" markerHeight="6" orient="0">
  41 |                         <path d="M 8 2 L 8 8 L 1 5 z" fill="#f56c6c" />
  42 |                     </marker>
  43 | 
  44 |                     <marker id="arrow-preview" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
  45 |                         <path d="M 0 2 L 10 5 L 0 8 z" fill="#4ed19c" />
  46 |                     </marker>
  47 |                 </defs>
  48 | 
  49 |                 <rect x="-5000" y="-5000" width="15000" height="15000" fill="url(#grid-pattern)" pointer-events="none" />
  50 | 
  51 |                 <!-- 纯净流光连线层 -->
  52 |                 <g v-for="edge in computedEdges" :key="edge.id">
  53 |                     <path :d="edge.path"
  54 |                           :class="['edge-path', { 'is-selected': edge.selected, 'is-danger': edge.isFail }]"
  55 |                           :marker-end="edge.markerUrl"
  56 |                           @click.stop="onEdgeClick(edge)" />
  57 |                     <path :d="edge.path"
  58 |                           :class="['edge-flow-path', { 'is-danger': edge.isFail }]"
  59 |                           pointer-events="none" />
  60 |                 </g>
  61 | 
  62 |                 <path v-if="drawingConnection.active" :d="drawingConnection.path" class="edge-path preview-path" :marker-end="drawingConnection.previewMarkerUrl" />
  63 |             </svg>
  64 | 
  65 |             <!-- 任务组包围框 -->
  66 |             <div v-for="group in dynamicGroups"
  67 |                  :key="group.groupId"
  68 |                  :data-group-id="group.groupId"
  69 |                  :class="['canvas-group-box', { 'is-focused': activeFocusedGroupId === group.groupId }]"
  70 |                  :style="{
  71 |              left: group.box.x + 'px',
  72 |              top: group.box.y + 'px',
  73 |              width: group.box.w + 'px',
  74 |              height: group.box.h + 'px'
  75 |            }">
  76 |                 <div class="group-title-badge" :data-group-id="group.groupId" @mousedown.stop="startGroupDrag($event, group.groupId)" @dblclick.stop="openGroupInspector($event, group)">
  77 |                     <div class="group-name-text">📁 {{ group.groupName }}</div>
  78 |                     <div class="group-sub-info">
  79 |                         <span>间隔: {{ group.loopInterval || 0 }}s</span>
  80 |                         <span>循环: {{ group.loopCount }}次</span>
  81 |                     </div>
  82 |                 </div>
  83 |             </div>
  84 | 
  85 |             <!-- 节点拖拽预览框 -->
  86 |             <div v-if="draggingNodeId && dragPreviewBox.visible"
  87 |                  class="node-drag-preview-box"
  88 |                  :class="{ 'is-danger': dragPreviewBox.hasCollision }"
  89 |                  :style="{
  90 |              left: dragPreviewBox.x + 'px',
  91 |              top: dragPreviewBox.y + 'px',
  92 |              width: dragPreviewBox.w + 'px',
  93 |              height: dragPreviewBox.h + 'px'
  94 |            }">
  95 |                 <div class="preview-inner-tag">
  96 |                     {{ dragPreviewBox.hasCollision ? '⚠️ 将自动推挤周围节点' : '✔️ 空间充足' }}
  97 |                 </div>
  98 |             </div>
  99 | 
 100 |             <!-- 节点卡片层 -->
 101 |             <div v-for="node in renderNodes"
 102 |                  :key="node.node_id"
 103 |                  :data-node-id="node.node_id"
 104 |                  :class="['canvas-node-card', { 'is-selected': node.selected }]"
 105 |                  :style="{ left: node.position.x + 'px', top: node.position.y + 'px', width: node.w + 'px', height: node.h + 'px' }"
 106 |                  @mousedown.stop="onNodeMouseDown($event, node)"
 107 |                  @mouseup="onNodeMouseUpCard($event, node)"
 108 |                  @dblclick.stop="onNodeDoubleClick($event, node)">
 109 |                 <!-- 1. 卡片头部：左侧图标 + 名称 -->
 110 |                 <div class="node-header" :data-node-id="node.node_id">
 111 |                     <div class="node-header-left" :data-node-id="node.node_id">
 112 |                         <component :is="getNodeIcon(node.node_type)" class="node-type-icon" />
 113 |                         <span class="node-title" :data-node-id="node.node_id">{{ node.node_name }}</span>
 114 |                     </div>
 115 |                 </div>
 116 | 
 117 |                 <!-- 2. 卡片中间主体区 -->
 118 |                 <div class="node-body" :data-node-id="node.node_id">
 119 |                     <!-- 图像识别节点预览 -->
 120 |                     <div v-if="node.node_type === 'image_recognition'"
 121 |                          class="node-image-embedded"
 122 |                          :style="node.params?.image_source ? { '--bg-image-url': `url(${getImageThumbnailUrl(node.params.image_source)})` } : {}">
 123 |                         <img v-if="node.params?.image_source"
 124 |                              :src="getImageThumbnailUrl(node.params.image_source)"
 125 |                              :class="['embedded-template-img', { 'is-contain': isSpecialTallImage(node.node_id) }]"
 126 |                              alt="模板"
 127 |                              @load="(e) => onImageLoaded(e, node.node_id)"
 128 |                              @error="$event.target.style.display = 'none'" />
 129 |                         <div v-else class="embedded-placeholder">
 130 |                             <Image style="width: 16px; height: 16px; opacity: 0.5; margin-bottom: 2px;" />
 131 |                             <span>未选模板</span>
 132 |                         </div>
 133 |                     </div>
 134 | 
 135 |                     <!-- ⚡ 分支选择 Branch 节点: 行级条件与专属出口锚点 -->
 136 |                     <div v-else-if="node.node_type === 'branch'" class="branch-candidates-list">
 137 |                         <div v-for="(cand, cIdx) in (node.params?.candidates || [])"
 138 |                              :key="cIdx"
 139 |                              class="branch-candidate-item">
 140 |                             <span class="branch-cand-text" :title="formatCondDesc(cand.condition || cand)">
 141 |                                 {{ formatCondDesc(cand.condition || cand) }}
 142 |                             </span>
 143 |                             <div class="node-handle source-handle branch-handle"
 144 |                                  :title="`分支 ${cIdx + 1} 成立时流向出口`"
 145 |                                  @mousedown.stop="startConnection($event, node.node_id, `branch_${cIdx}`)" />
 146 |                         </div>
 147 |                         <div v-if="!node.params?.candidates?.length" class="empty-cand-placeholder">
 148 |                             <span>未配置分流条件</span>
 149 |                         </div>
 150 |                     </div>
 151 |                 </div>
 152 | 
 153 |                 <!-- 3. 卡片底部固定边栏 -->
 154 |                 <div class="node-footer-bar" :data-node-id="node.node_id">
 155 |                     <span class="footer-tag">延时: {{ node.delay_before ?? 200 }}ms</span>
 156 |                     <span class="footer-tag">循环: {{ node.loop_count ?? 1 }}次</span>
 157 |                 </div>
 158 | 
 159 |                 <!-- 通用入口与失败/兜底锚点 -->
 160 |                 <div class="node-handle target-handle top-handle" title="入口位置" />
 161 |                 <div v-if="node.node_type !== 'branch'" class="node-handle source-handle succ-handle" title="成功流向出口" @mousedown.stop="startConnection($event, node.node_id, 'succ')" />
 162 |                 <div v-if="node.showFailPort" class="node-handle source-handle fail-handle" :title="node.node_type === 'branch' ? 'Else 兜底分支出口' : '失败分支出口'" @mousedown.stop="startConnection($event, node.node_id, 'fail')" />
 163 |             </div>
 164 | 
 165 |         </div>
 166 | 
 167 |         <!-- 全景缩略图导航面板 -->
 168 |         <div class="minimap-container" v-show="store.minimapExpanded">
 169 |             <canvas ref="minimapCanvasRef" width="150" height="110" @click="onMinimapClick" />
 170 |         </div>
 171 | 
 172 |         <!-- 框选 UI -->
 173 |         <div v-if="selectionBox.visible" class="selection-box" :style="selectionBoxStyle" />
 174 | 
 175 |         <!-- 节点类型选择菜单 -->
 176 |         <div v-if="spawnMenu.visible"
 177 |              class="spawn-menu"
 178 |              :style="{ left: spawnMenu.x + 'px', top: spawnMenu.y + 'px', zIndex: menuZIndex }"
 179 |              @mousedown.stop
 180 |              @click.stop>
 181 |             <div class="spawn-menu-header">
 182 |                 ⚡ {{ spawnMenu.sourceNodeId ? `快捷创建并连接` : '✨ 选择新建节点类型' }}
 183 |             </div>
 184 |             <div class="spawn-menu-list">
 185 |                 <div v-for="(label, type) in availableNodeTypes" :key="type" class="spawn-menu-item" @click="createAndConnectNode(type)">
 186 |                     {{ label }}
 187 |                 </div>
 188 |             </div>
 189 |         </div>
 190 | 
 191 |         <!-- 画布空白处右键菜单 -->
 192 |         <div v-if="customContextMenu.visible"
 193 |              class="custom-context-menu"
 194 |              :style="{ left: customContextMenu.x + 'px', top: customContextMenu.y + 'px', zIndex: menuZIndex }"
 195 |              @mousedown.stop
 196 |              @click.stop>
 197 |             <template v-if="customContextMenu.targetType === 'node'">
 198 |                 <div class="menu-item" @click="handleRunFromNode">
 199 |                     <CirclePlay class="menu-item-icon" style="color: var(--el-color-primary);" />
 200 |                     <span>从此节点开始运行</span>
 201 |                 </div>
 202 |                 <div class="menu-item danger" @click="handleDeleteNode">
 203 |                     <Trash2 class="menu-item-icon" />
 204 |                     <span>删除节点</span>
 205 |                 </div>
 206 |             </template>
 207 | 
 208 |             <template v-else-if="customContextMenu.targetType === 'group'">
 209 |                 <div class="menu-item danger" @click="handleDeleteGroup">
 210 |                     <Trash2 class="menu-item-icon" />
 211 |                     <span>删除组</span>
 212 |                 </div>
 213 |             </template>
 214 | 
 215 |             <template v-else-if="customContextMenu.targetType === 'canvas_in_group'">
 216 |                 <div class="menu-item" @click="handleCanvasNewNode">
 217 |                     📁 在当前组 [{{ customContextMenu.targetName }}] 新建节点
 218 |                 </div>
 219 |                 <div class="menu-item" @click="handleCanvasNewGroup">
 220 |                     📁 新建任务组
 221 |                 </div>
 222 |             </template>
 223 | 
 224 |             <template v-else-if="customContextMenu.targetType === 'canvas_public'">
 225 |                 <div class="menu-item" @click="handleCanvasNewNode">
 226 |                     ✨ 在新建组中新建节点
 227 |                 </div>
 228 |                 <div class="menu-item" @click="handleCanvasNewGroup">
 229 |                     📁 新建任务组
 230 |                 </div>
 231 |             </template>
 232 | 
 233 |             <template v-else>
 234 |                 <div class="menu-item" @click="handleCanvasNewGroup">
 235 |                     📁 新建任务组
 236 |                 </div>
 237 |                 <div class="menu-item" @click="handleCanvasNewNode">
 238 |                     ✨ 新建节点
 239 |                 </div>
 240 |             </template>
 241 |         </div>
 242 |     </div>
 243 | </template>
 244 | 
 245 | <script setup>
 246 |     import { ref, computed, onMounted, onUnmounted, reactive, nextTick, watch } from 'vue'
 247 |     import { useMainStore } from '@/stores'
 248 |     import { ElMessage, ElMessageBox } from 'element-plus'
 249 |     import { blueprintApi } from '@/api/blueprintApi'
 250 |     import { router } from '@/utils/gridRouter'
 251 |     import { getRoundedPathString } from '@/utils/pathSmooth'
 252 |     import { getNextZIndex } from '@/utils/zIndexManager'
 253 | 
 254 |     import {
 255 |         MousePointerClick, Clock, Target, FileSearch, GitBranch, SearchCheck,
 256 |         Binary, ListOrdered, FileCode, Image, CirclePlay, Trash2
 257 |     } from 'lucide-vue-next'
 258 | 
 259 |     const store = useMainStore()
 260 |     const containerRef = ref(null)
 261 |     const minimapCanvasRef = ref(null)
 262 |     const menuZIndex = ref(3000)
 263 |     const isCtrlHeldRef = ref(false)
 264 |     const draggedSourceGroupSnapshot = ref(null)
 265 |     const ghostPlaceholder = ref(null)
 266 | 
 267 |     const viewport = ref({ x: 0, y: 0, zoom: 1 })
 268 |     const isPanning = ref(false)
 269 |     const panStart = ref({ x: 0, y: 0 })
 270 | 
 271 |     const localDraftPositions = reactive({})
 272 |     const draggingNodeId = ref(null)
 273 |     const dragStartMouse = ref({ x: 0, y: 0 })
 274 |     const nodeInitialPos = ref({ x: 0, y: 0 })
 275 |     const hasMoved = ref(false)
 276 | 
 277 |     const dynamicImageHeights = reactive({})
 278 |     const tallImageFlags = reactive({})
 279 | 
 280 |     const dragPreviewBox = ref({ visible: false, x: 0, y: 0, w: 0, h: 0, hasCollision: false })
 281 |     const selectionBox = ref({ visible: false, startX: 0, startY: 0, endX: 0, endY: 0 })
 282 |     const drawingConnection = ref({ active: false, sourceNodeId: null, portType: 'succ', currentX: 0, currentY: 0, previewMarkerUrl: 'url(#arrow-preview)' })
 283 | 
 284 |     const spawnMenu = ref({ visible: false, x: 0, y: 0, sourceNodeId: null, portType: 'succ', clientX: 0, clientY: 0 })
 285 | 
 286 |     const customContextMenu = reactive({
 287 |         visible: false,
 288 |         x: 0,
 289 |         y: 0,
 290 |         targetType: 'canvas',
 291 |         targetId: null,
 292 |         targetName: '',
 293 |         clientX: 0,
 294 |         clientY: 0
 295 |     })
 296 | 
 297 |     const selectedEdgeId = ref(null)
 298 |     const localSelectedNodeIds = ref([])
 299 | 
 300 |     const GRID_SIZE = 20
 301 |     const NODE_GRID_W = 8
 302 | 
 303 |     const availableNodeTypes = {
 304 |         click: '🖱️ 鼠标点击',
 305 |         wait: '⏳ 等待',
 306 |         image_recognition: '🎯 图像识别',
 307 |         ocr_recognition: '👁️ 文字识别 (OCR)',
 308 |         branch: '🔀 分支选择',
 309 |         logic_check: '🔍 逻辑判断',
 310 |         variable_op: '🔢 变量操作',
 311 |         log: '📝 日志输出',
 312 |         script_call: '📜 调用脚本'
 313 |     }
 314 | 
 315 |     const nodeIconComponentMap = {
 316 |         click: MousePointerClick,
 317 |         wait: Clock,
 318 |         set_window: Target,
 319 |         image_recognition: Image,
 320 |         ocr_recognition: FileSearch,
 321 |         branch: GitBranch,
 322 |         logic_check: SearchCheck,
 323 |         variable_op: Binary,
 324 |         log: ListOrdered,
 325 |         script_call: FileCode
 326 |     }
 327 | 
 328 |     const getNodeIcon = (nodeType) => nodeIconComponentMap[nodeType] || FileCode
 329 | 
 330 |     const getNodeShortLabel = (nodeType) => {
 331 |         const label = availableNodeTypes[nodeType] || nodeType
 332 |         return label.replace(/^[^\u4e00-\u9fa5]+/, '').trim()
 333 |     }
 334 | 
 335 |     // ⚡ 格式化 Branch 条件的纯简描述
 336 |     const formatCondDesc = (item) => {
 337 |         if (!item) return '未配置条件'
 338 |         const condType = item.condition_type || item.type || 'variable_check'
 339 |         const params = item.params || item
 340 | 
 341 |         if (condType === 'image_exists') {
 342 |             const opText = params.exist_mode === 'not_exists' ? '不存在' : '存在'
 343 |             return `🖼️ ${opText}: ${params.image_source || '未选图片'}`
 344 |         }
 345 |         if (condType === 'text_contains') {
 346 |             return `🔤 文本: ${params.target_text || '未设文本'}`
 347 |         }
 348 |         if (condType === 'variable_check') {
 349 |             return `🔢 变量: ${params.variable_name || params.var_name || '未选'} (${params.operator || 'eq'}) ${params.compare_value ?? params.target_value ?? ''}`
 350 |         }
 351 |         if (condType === 'window_state') {
 352 |             return `🪟 窗口: ${params.window_title || '默认'} (${params.state_check || '存在'})`
 353 |         }
 354 |         if (condType === 'file_exists') {
 355 |             return `📂 文件: ${params.file_path || '未设路径'}`
 356 |         }
 357 |         return `判定: ${condType}`
 358 |     }
 359 | 
 360 |     const getImageThumbnailUrl = (imageSource) => {
 361 |         if (!imageSource) return ''
 362 |         let cleanName = imageSource.replace(/\\/g, '/')
 363 |         if (!/\.(png|jpg|jpeg)$/i.test(cleanName)) cleanName += '.png'
 364 |         const version = store.blueprint?.version || 0
 365 |         return `/api/image/thumb?project_path=${encodeURIComponent(store.currentProjectPath || '')}&name=${encodeURIComponent(cleanName)}&v=${version}`
 366 |     }
 367 | 
 368 |     const hasFailurePort = (nodeType) => ['image_recognition', 'ocr_recognition', 'branch', 'logic_check'].includes(nodeType)
 369 | 
 370 |     const viewportStyle = computed(() => ({
 371 |         transform: `translate(${viewport.value.x}px, ${viewport.value.y}px) scale(${viewport.value.zoom})`,
 372 |         transformOrigin: '0 0'
 373 |     }))
 374 | 
 375 |     const selectionBoxStyle = computed(() => {
 376 |         if (!containerRef.value) return {}
 377 |         const rect = containerRef.value.getBoundingClientRect()
 378 |         const startX = selectionBox.value.startX - rect.left
 379 |         const startY = selectionBox.value.startY - rect.top
 380 |         const endX = selectionBox.value.endX - rect.left
 381 |         const endY = selectionBox.value.endY - rect.top
 382 |         return {
 383 |             left: Math.min(startX, endX) + 'px',
 384 |             top: Math.min(startY, endY) + 'px',
 385 |             width: Math.abs(endX - startX) + 'px',
 386 |             height: Math.abs(endY - startY) + 'px'
 387 |         }
 388 |     })
 389 | 
 390 |     const activeFocusedGroupId = computed(() => {
 391 |         if (draggingNodeId.value) {
 392 |             const tasks = store.blueprint?.tasks || []
 393 |             for (let i = 0; i < tasks.length; i++) {
 394 |                 if ((tasks[i].nodes || []).some(n => n.node_id === draggingNodeId.value)) {
 395 |                     return `group_${tasks[i].task_id || i}`
 396 |                 }
 397 |             }
 398 |         }
 399 |         if (localSelectedNodeIds.value.length > 0) {
 400 |             const firstSelId = localSelectedNodeIds.value[0]
 401 |             const tasks = store.blueprint?.tasks || []
 402 |             for (let i = 0; i < tasks.length; i++) {
 403 |                 if ((tasks[i].nodes || []).some(n => n.node_id === firstSelId)) {
 404 |                     return `group_${tasks[i].task_id || i}`
 405 |                 }
 406 |             }
 407 |         }
 408 |         return null
 409 |     })
 410 | 
 411 |     // ⚡ 计算 Branch 行级出口相对 Y 轴中心位置
 412 |     const getBranchPortCenterY = (node, cIdx) => {
 413 |         // 卡片顶边距 8 + 头部 16 + 容器边距 4 + 列表边距 2 + 单项中心 12 = 42px，单项高度加间距步长为 28px
 414 |         return 42 + cIdx * 28
 415 |     }
 416 | 
 417 |     const renderNodes = computed(() => {
 418 |         const tasks = store.blueprint?.tasks || []
 419 |         let allNodesList = []
 420 | 
 421 |         tasks.forEach((task) => {
 422 |             const rawNodes = task.nodes || []
 423 |             rawNodes.forEach((node, nIndex) => {
 424 |                 const rawPos = localDraftPositions[node.node_id] || node.position || { x: 60 + (nIndex % 3) * 200, y: 60 + Math.floor(nIndex / 3) * 120 }
 425 |                 const gridX = Math.round(rawPos.x / GRID_SIZE) * GRID_SIZE
 426 |                 const gridY = Math.round(rawPos.y / GRID_SIZE) * GRID_SIZE
 427 |                 const isSel = localSelectedNodeIds.value.includes(node.node_id)
 428 | 
 429 |                 let contentHeightPx = 52
 430 |                 if (node.node_type === 'image_recognition') {
 431 |                     if (dynamicImageHeights[node.node_id]) {
 432 |                         contentHeightPx += dynamicImageHeights[node.node_id]
 433 |                     } else {
 434 |                         contentHeightPx += 120
 435 |                     }
 436 |                 } else if (node.node_type === 'branch') {
 437 |                     const candCount = node.params?.candidates?.length || 0
 438 |                     contentHeightPx += Math.max(candCount * 28, 30)
 439 |                 }
 440 | 
 441 |                 const exactGrids = contentHeightPx / GRID_SIZE
 442 |                 const gridCount = Math.ceil(exactGrids)
 443 |                 const finalHeight = gridCount * GRID_SIZE
 444 | 
 445 |                 allNodesList.push({
 446 |                     ...node,
 447 |                     position: { x: gridX, y: gridY },
 448 |                     w: NODE_GRID_W * GRID_SIZE,
 449 |                     h: finalHeight,
 450 |                     showFailPort: hasFailurePort(node.node_type),
 451 |                     selected: isSel
 452 |                 })
 453 |             })
 454 |         })
 455 |         return allNodesList
 456 |     })
 457 | 
 458 |     const onImageLoaded = (e, nodeId) => {
 459 |         const img = e.target
 460 |         const naturalW = img.naturalWidth || 100
 461 |         const naturalH = img.naturalHeight || 100
 462 |         const cardInnerWidth = (NODE_GRID_W * GRID_SIZE) - 24
 463 | 
 464 |         const ratio = naturalH / naturalW
 465 |         if (ratio > 1) {
 466 |             tallImageFlags[nodeId] = true
 467 |             dynamicImageHeights[nodeId] = cardInnerWidth
 468 |         } else {
 469 |             tallImageFlags[nodeId] = false
 470 |             dynamicImageHeights[nodeId] = Math.round(cardInnerWidth * ratio)
 471 |         }
 472 |     }
 473 | 
 474 |     const isSpecialTallImage = (nodeId) => !!tallImageFlags[nodeId]
 475 | 
 476 |     const fitViewToNodes = () => {
 477 |         nextTick(() => {
 478 |             const tasks = store.blueprint?.tasks || []
 479 |             let allNodes = []
 480 |             tasks.forEach(t => { if (t.nodes) allNodes.push(...t.nodes) })
 481 |             if (allNodes.length === 0 || !containerRef.value) return
 482 | 
 483 |             let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
 484 |             allNodes.forEach(n => {
 485 |                 const pos = n.position || { x: 0, y: 0 }
 486 |                 const w = NODE_GRID_W * GRID_SIZE
 487 |                 const h = n.h || 120
 488 |                 minX = Math.min(minX, pos.x)
 489 |                 minY = Math.min(minY, pos.y)
 490 |                 maxX = Math.max(maxX, pos.x + w)
 491 |                 maxY = Math.max(maxY, pos.y + h)
 492 |             })
 493 | 
 494 |             const centerX = (minX + maxX) / 2
 495 |             const centerY = (minY + maxY) / 2
 496 | 
 497 |             const containerW = containerRef.value.clientWidth
 498 |             const containerH = containerRef.value.clientHeight
 499 | 
 500 |             viewport.value.x = containerW / 2 - centerX * viewport.value.zoom
 501 |             viewport.value.y = containerH / 2 - centerY * viewport.value.zoom
 502 | 
 503 |             drawMinimap()
 504 |         })
 505 |     }
 506 | 
 507 |     const dynamicGroups = computed(() => {
 508 |         const tasks = store.blueprint?.tasks || []
 509 |         let groups = []
 510 |         const PADDING_GRIDS = 3
 511 |         const PADDING_PX = PADDING_GRIDS * GRID_SIZE
 512 | 
 513 |         const allRenderedNodes = renderNodes.value
 514 | 
 515 |         tasks.forEach((task, tIndex) => {
 516 |             const groupId = `group_${task.task_id || tIndex}`
 517 |             const groupName = task.task_name || `任务组 ${tIndex + 1}`
 518 | 
 519 |             const taskNodeIds = (task.nodes || []).map(n => n.node_id)
 520 |             const groupNodes = allRenderedNodes.filter(n => {
 521 |                 if (!taskNodeIds.includes(n.node_id)) return false
 522 |                 if (n.node_id === draggingNodeId.value && isCtrlHeldRef.value) {
 523 |                     return false
 524 |                 }
 525 |                 return true
 526 |             })
 527 | 
 528 |             let effectiveNodes = [...groupNodes]
 529 |             if (ghostPlaceholder.value && draggingNodeId.value && isCtrlHeldRef.value) {
 530 |                 const isNodeInThisGroup = taskNodeIds.includes(draggingNodeId.value)
 531 |                 if (isNodeInThisGroup) {
 532 |                     effectiveNodes.push(ghostPlaceholder.value)
 533 |                 }
 534 |             }
 535 | 
 536 |             let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
 537 | 
 538 |             if (effectiveNodes.length > 0) {
 539 |                 effectiveNodes.forEach((node) => {
 540 |                     minX = Math.min(minX, node.position.x)
 541 |                     minY = Math.min(minY, node.position.y)
 542 |                     maxX = Math.max(maxX, node.position.x + node.w)
 543 |                     maxY = Math.max(maxY, node.position.y + node.h)
 544 |                 })
 545 | 
 546 |                 const rawBoxX = minX - PADDING_PX
 547 |                 const rawBoxY = minY - PADDING_PX - 24
 548 |                 const rawBoxW = (maxX - minX) + PADDING_PX * 2
 549 |                 const rawBoxH = (maxY - minY) + PADDING_PX * 2 + 24
 550 | 
 551 |                 const boxX = Math.round(rawBoxX / GRID_SIZE) * GRID_SIZE
 552 |                 const boxY = Math.round(rawBoxY / GRID_SIZE) * GRID_SIZE
 553 |                 const boxW = Math.max(Math.round(rawBoxW / GRID_SIZE) * GRID_SIZE, 220)
 554 |                 const boxH = Math.max(Math.round(rawBoxH / GRID_SIZE) * GRID_SIZE, 120)
 555 | 
 556 |                 groups.push({
 557 |                     groupId,
 558 |                     groupName,
 559 |                     taskId: task.task_id,
 560 |                     loopCount: task.loop_count || 1,
 561 |                     loopInterval: task.loop_interval || 0,
 562 |                     box: { x: boxX, y: boxY, w: boxW, h: boxH }
 563 |                 })
 564 |             } else {
 565 |                 groups.push({
 566 |                     groupId,
 567 |                     groupName,
 568 |                     taskId: task.task_id,
 569 |                     loopCount: task.loop_count || 1,
 570 |                     loopInterval: task.loop_interval || 0,
 571 |                     box: { x: 60, y: 60, w: 240, h: 140 }
 572 |                 })
 573 |             }
 574 |         })
 575 |         return groups
 576 |     })
 577 | 
 578 |     const onContextMenu = (e) => {
 579 |         e.preventDefault()
 580 |         menuZIndex.value = getNextZIndex(e)
 581 |         customContextMenu.visible = false
 582 | 
 583 |         const nodeCard = e.target.closest('.canvas-node-card')
 584 |         if (nodeCard) {
 585 |             const nodeId = nodeCard.getAttribute('data-node-id')
 586 |             const nodeObj = renderNodes.value.find(n => n.node_id === nodeId)
 587 |             if (nodeObj) {
 588 |                 customContextMenu.visible = true
 589 |                 customContextMenu.x = e.clientX
 590 |                 customContextMenu.y = e.clientY
 591 |                 customContextMenu.targetType = 'node'
 592 |                 customContextMenu.targetId = nodeObj.node_id
 593 |                 customContextMenu.targetName = nodeObj.node_name
 594 |                 customContextMenu.clientX = e.clientX
 595 |                 customContextMenu.clientY = e.clientY
 596 |                 return
 597 |             }
 598 |         }
 599 | 
 600 |         const groupBox = e.target.closest('.canvas-group-box') || e.target.closest('.group-title-badge')
 601 |         if (groupBox) {
 602 |             const groupId = groupBox.getAttribute('data-group-id')
 603 |             const groupObj = dynamicGroups.value.find(g => g.groupId === groupId)
 604 |             if (groupObj) {
 605 |                 customContextMenu.visible = true
 606 |                 customContextMenu.x = e.clientX
 607 |                 customContextMenu.y = e.clientY
 608 |                 customContextMenu.targetType = 'group'
 609 |                 customContextMenu.targetId = groupObj.taskId
 610 |                 customContextMenu.targetName = groupObj.groupName
 611 |                 customContextMenu.clientX = e.clientX
 612 |                 customContextMenu.clientY = e.clientY
 613 |                 return
 614 |             }
 615 |         }
 616 | 
 617 |         if (!containerRef.value) return
 618 |         const rect = containerRef.value.getBoundingClientRect()
 619 |         const clientX = e.clientX - rect.left
 620 |         const clientY = e.clientY - rect.top
 621 |         const worldX = (clientX - viewport.value.x) / viewport.value.zoom
 622 |         const worldY = (clientY - viewport.value.y) / viewport.value.zoom
 623 | 
 624 |         let hitGroup = null
 625 |         for (const g of dynamicGroups.value) {
 626 |             const box = g.box
 627 |             if (worldX >= box.x && worldX <= box.x + box.w && worldY >= box.y && worldY <= box.y + box.h) {
 628 |                 hitGroup = g
 629 |                 break
 630 |             }
 631 |         }
 632 | 
 633 |         customContextMenu.visible = true
 634 |         customContextMenu.x = e.clientX
 635 |         customContextMenu.y = e.clientY
 636 |         customContextMenu.clientX = e.clientX
 637 |         customContextMenu.clientY = e.clientY
 638 | 
 639 |         if (hitGroup) {
 640 |             customContextMenu.targetType = 'canvas_in_group'
 641 |             customContextMenu.targetId = hitGroup.taskId
 642 |             customContextMenu.targetName = hitGroup.groupName
 643 |         } else {
 644 |             customContextMenu.targetType = 'canvas_public'
 645 |             customContextMenu.targetId = null
 646 |             customContextMenu.targetName = ''
 647 |         }
 648 |     }
 649 | 
 650 |     const handleRunFromNode = async () => {
 651 |         const nodeId = customContextMenu.targetId
 652 |         customContextMenu.visible = false
 653 |         if (!nodeId) return
 654 | 
 655 |         let targetTaskId = null
 656 |         const tasks = store.blueprint?.tasks || []
 657 |         for (const task of tasks) {
 658 |             if ((task.nodes || []).some(n => n.node_id === nodeId)) {
 659 |                 targetTaskId = task.task_id
 660 |                 break
 661 |             }
 662 |         }
 663 | 
 664 |         if (!targetTaskId) {
 665 |             ElMessage.error('未找到该节点所属的任务组')
 666 |             return
 667 |         }
 668 | 
 669 |         try {
 670 |             ElMessage.info('正在从当前节点启动任务...')
 671 |             const result = await store.runTask(targetTaskId, nodeId)
 672 |             if (result && result.status === 'started') {
 673 |                 ElMessage.success('任务已成功从当前节点启动！')
 674 |             } else {
 675 |                 ElMessage.error('执行失败')
 676 |             }
 677 |         } catch (err) {
 678 |             ElMessage.error('执行请求失败: ' + err.message)
 679 |         }
 680 |     }
 681 | 
 682 |     const handleDeleteNode = async () => {
 683 |         const nodeId = customContextMenu.targetId
 684 |         customContextMenu.visible = false
 685 |         if (!nodeId) return
 686 | 
 687 |         try {
 688 |             const tasks = store.blueprint?.tasks || []
 689 |             for (const task of tasks) {
 690 |                 if (task.nodes) {
 691 |                     task.nodes = task.nodes.filter(n => n.node_id !== nodeId)
 692 |                 }
 693 |             }
 694 |             store.blueprint.tasks = tasks.filter(t => (t.nodes || []).length > 0)
 695 |             await store.saveBlueprintImmediately()
 696 |             ElMessage.success('节点已成功删除')
 697 |         } catch (err) {
 698 |             ElMessage.error('删除节点失败: ' + err.message)
 699 |         }
 700 |     }
 701 | 
 702 |     const handleDeleteGroup = async () => {
 703 |         const taskId = customContextMenu.targetId
 704 |         customContextMenu.visible = false
 705 |         if (!taskId) return
 706 | 
 707 |         try {
 708 |             await blueprintApi.deleteTask(taskId, store.currentProjectPath)
 709 |             await store.loadProjectData()
 710 |             ElMessage.success('任务组已成功删除')
 711 |         } catch (err) {
 712 |             ElMessage.error('删除任务组失败: ' + err.message)
 713 |         }
 714 |     }
 715 | 
 716 |     const handleCanvasNewNode = () => {
 717 |         customContextMenu.visible = false
 718 |         spawnMenu.value = {
 719 |             visible: true,
 720 |             x: customContextMenu.x,
 721 |             y: customContextMenu.y,
 722 |             sourceNodeId: null,
 723 |             portType: 'succ',
 724 |             clientX: customContextMenu.clientX,
 725 |             clientY: customContextMenu.clientY
 726 |         }
 727 |     }
 728 | 
 729 |     const handleCanvasNewGroup = async () => {
 730 |         customContextMenu.visible = false
 731 |         try {
 732 |             const { value: groupName } = await ElMessageBox.prompt('请输入新任务组名称', '新建任务组', {
 733 |                 confirmButtonText: '确定',
 734 |                 cancelButtonText: '取消',
 735 |                 inputPattern: /\S+/,
 736 |                 inputErrorMessage: '任务组名称不能为空'
 737 |             })
 738 | 
 739 |             if (groupName) {
 740 |                 await blueprintApi.createTask(store.currentProjectPath, { task_name: groupName.trim(), nodes: [] })
 741 |                 await store.loadProjectData()
 742 |                 ElMessage.success(`任务组 [${groupName}] 创建成功`)
 743 |             }
 744 |         } catch (err) {
 745 |             if (err !== 'cancel') {
 746 |                 ElMessage.error(err.message || '创建任务组失败')
 747 |             }
 748 |         }
 749 |     }
 750 | 
 751 |     const getArrowDirection = (points) => {
 752 |         if (!points || points.length < 2) return 'down'
 753 |         let p1 = points[points.length - 2]
 754 |         let p2 = points[points.length - 1]
 755 | 
 756 |         for (let i = points.length - 1; i > 0; i--) {
 757 |             if (points[i].x !== points[i - 1].x || points[i].y !== points[i - 1].y) {
 758 |                 p2 = points[i]
 759 |                 p1 = points[i - 1]
 760 |                 break
 761 |             }
 762 |         }
 763 | 
 764 |         const dx = p2.x - p1.x
 765 |         const dy = p2.y - p1.y
 766 | 
 767 |         let dir = 'down'
 768 |         if (Math.abs(dx) >= Math.abs(dy)) {
 769 |             dir = dx > 0 ? 'right' : 'left'
 770 |         } else {
 771 |             dir = dy > 0 ? 'down' : 'up'
 772 |         }
 773 |         return dir
 774 |     }
 775 | 
 776 |     // ⚡ 核心连线计算：支持常规成功、行级分支（branch_i）与 Else/失败兜底出口
 777 |     const computedEdges = computed(() => {
 778 |         let edges = []
 779 |         const allNodes = renderNodes.value
 780 |         const activeDraggingId = draggingNodeId.value
 781 |         const isActuallyMoving = hasMoved.value
 782 | 
 783 |         allNodes.forEach(node => {
 784 |             // 1. 普通节点常规成功出口
 785 |             if (node.node_type !== 'branch' && node.params?.on_success?.target_node) {
 786 |                 const target = allNodes.find(n => n.node_id === node.params.on_success.target_node)
 787 |                 if (target) {
 788 |                     let smoothPathStr = ''
 789 |                     let arrowDir = 'down'
 790 |                     let routeResult = null
 791 | 
 792 |                     const isThisEdgeDragging = activeDraggingId && isActuallyMoving && (node.node_id === activeDraggingId || target.node_id === activeDraggingId)
 793 | 
 794 |                     if (isThisEdgeDragging) {
 795 |                         const startPt = { x: node.position.x + node.w / 2, y: node.position.y + node.h }
 796 |                         const endPt = { x: target.position.x + target.w / 2, y: target.position.y }
 797 |                         const simplePoints = [startPt, { x: startPt.x, y: (startPt.y + endPt.y) / 2 }, { x: endPt.x, y: (startPt.y + endPt.y) / 2 }, endPt]
 798 |                         smoothPathStr = getRoundedPathString(simplePoints, 10)
 799 |                         arrowDir = getArrowDirection(simplePoints)
 800 |                         routeResult = { startPt, endPt }
 801 |                     } else {
 802 |                         const rr = router.route(node, target, allNodes, 'succ', true)
 803 |                         routeResult = rr
 804 |                         smoothPathStr = getRoundedPathString(rr.rawPixelPoints, 10)
 805 |                         arrowDir = getArrowDirection(rr.rawPixelPoints)
 806 |                     }
 807 | 
 808 |                     const edgeId = `e_${node.node_id}_succ_${target.node_id}`
 809 |                     edges.push({
 810 |                         id: edgeId,
 811 |                         sourceNodeId: node.node_id,
 812 |                         targetNodeId: target.node_id,
 813 |                         typeFlag: 'succ',
 814 |                         path: smoothPathStr,
 815 |                         isFail: false,
 816 |                         markerUrl: `url(#arrow-succ-${arrowDir})`,
 817 |                         selected: selectedEdgeId.value === edgeId,
 818 |                         labelX: (routeResult.startPt.x + routeResult.endPt.x) / 2,
 819 |                         labelY: (routeResult.startPt.y + routeResult.endPt.y) / 2 - 10,
 820 |                         rawPixelPoints: routeResult.rawPixelPoints || []
 821 |                     })
 822 |                 }
 823 |             }
 824 | 
 825 |             // 2. Branch 节点：多路行级分支出口 (branch_0, branch_1...)
 826 |             if (node.node_type === 'branch' && Array.isArray(node.params?.candidates)) {
 827 |                 node.params.candidates.forEach((cand, cIdx) => {
 828 |                     if (cand?.on_success?.target_node) {
 829 |                         const target = allNodes.find(n => n.node_id === cand.on_success.target_node)
 830 |                         if (target) {
 831 |                             let smoothPathStr = ''
 832 |                             let arrowDir = 'right'
 833 |                             let routeResult = null
 834 |                             const portType = `branch_${cIdx}`
 835 | 
 836 |                             const isThisEdgeDragging = activeDraggingId && isActuallyMoving && (node.node_id === activeDraggingId || target.node_id === activeDraggingId)
 837 | 
 838 |                             if (isThisEdgeDragging) {
 839 |                                 const startPt = { x: node.position.x + node.w, y: node.position.y + getBranchPortCenterY(node, cIdx) }
 840 |                                 const endPt = { x: target.position.x + target.w / 2, y: target.position.y }
 841 |                                 const simplePoints = [startPt, { x: startPt.x + 20, y: startPt.y }, { x: endPt.x, y: (startPt.y + endPt.y) / 2 }, endPt]
 842 |                                 smoothPathStr = getRoundedPathString(simplePoints, 10)
 843 |                                 arrowDir = getArrowDirection(simplePoints)
 844 |                                 routeResult = { startPt, endPt }
 845 |                             } else {
 846 |                                 const rr = router.route(node, target, allNodes, portType, true)
 847 |                                 routeResult = rr
 848 |                                 smoothPathStr = getRoundedPathString(rr.rawPixelPoints, 10)
 849 |                                 arrowDir = getArrowDirection(rr.rawPixelPoints)
 850 |                             }
 851 | 
 852 |                             const edgeId = `e_${node.node_id}_branch_${cIdx}_${target.node_id}`
 853 |                             edges.push({
 854 |                                 id: edgeId,
 855 |                                 sourceNodeId: node.node_id,
 856 |                                 targetNodeId: target.node_id,
 857 |                                 typeFlag: 'branch',
 858 |                                 candIndex: cIdx,
 859 |                                 path: smoothPathStr,
 860 |                                 isFail: false,
 861 |                                 markerUrl: `url(#arrow-succ-${arrowDir})`,
 862 |                                 selected: selectedEdgeId.value === edgeId,
 863 |                                 labelX: (routeResult.startPt.x + routeResult.endPt.x) / 2,
 864 |                                 labelY: (routeResult.startPt.y + routeResult.endPt.y) / 2 - 10,
 865 |                                 rawPixelPoints: routeResult.rawPixelPoints || []
 866 |                             })
 867 |                         }
 868 |                     }
 869 |                 })
 870 |             }
 871 | 
 872 |             // 3. 失败 / Else 兜底出口
 873 |             if (node.params?.on_failure?.target_node) {
 874 |                 const target = allNodes.find(n => n.node_id === node.params.on_failure.target_node)
 875 |                 if (target) {
 876 |                     let smoothPathStr = ''
 877 |                     let arrowDir = 'down'
 878 |                     let routeResult = null
 879 | 
 880 |                     const isThisEdgeDragging = activeDraggingId && isActuallyMoving && (node.node_id === activeDraggingId || target.node_id === activeDraggingId)
 881 | 
 882 |                     if (isThisEdgeDragging) {
 883 |                         // ⚡ Branch 节点 Else 兜底红点在右下方
 884 |                         const startOffsetY = node.node_type === 'branch' ? (node.h - 18) : (node.h / 2)
 885 |                         const startPt = { x: node.position.x + node.w, y: node.position.y + startOffsetY }
 886 |                         const endPt = { x: target.position.x + target.w / 2, y: target.position.y }
 887 |                         const simplePoints = [startPt, { x: (startPt.x + endPt.x) / 2, y: startPt.y }, { x: (startPt.x + endPt.x) / 2, y: endPt.y }, endPt]
 888 |                         smoothPathStr = getRoundedPathString(simplePoints, 10)
 889 |                         arrowDir = getArrowDirection(simplePoints)
 890 |                         routeResult = { startPt, endPt }
 891 |                     } else {
 892 |                         const rr = router.route(node, target, allNodes, 'fail')
 893 |                         routeResult = rr
 894 |                         smoothPathStr = getRoundedPathString(rr.rawPixelPoints, 10)
 895 |                         arrowDir = getArrowDirection(rr.rawPixelPoints)
 896 |                     }
 897 | 
 898 |                     const edgeId = `e_${node.node_id}_fail_${target.node_id}`
 899 |                     edges.push({
 900 |                         id: edgeId,
 901 |                         sourceNodeId: node.node_id,
 902 |                         targetNodeId: target.node_id,
 903 |                         typeFlag: 'fail',
 904 |                         path: smoothPathStr,
 905 |                         isFail: true,
 906 |                         markerUrl: `url(#arrow-fail-${arrowDir})`,
 907 |                         selected: selectedEdgeId.value === edgeId,
 908 |                         labelX: (routeResult.startPt.x + routeResult.endPt.x) / 2,
 909 |                         labelY: (routeResult.startPt.y + routeResult.endPt.y) / 2 - 10,
 910 |                         rawPixelPoints: routeResult.rawPixelPoints || []
 911 |                     })
 912 |                 }
 913 |             }
 914 |         })
 915 | 
 916 |         // 4. 用户实时拉线预览
 917 |         if (drawingConnection.value.active) {
 918 |             const sourceNode = allNodes.find(n => n.node_id === drawingConnection.value.sourceNodeId)
 919 |             if (sourceNode) {
 920 |                 let startPt = { x: 0, y: 0 }
 921 |                 const portType = drawingConnection.value.portType
 922 | 
 923 |                 if (portType === 'succ') {
 924 |                     startPt = { x: sourceNode.position.x + sourceNode.w / 2, y: sourceNode.position.y + sourceNode.h }
 925 |                 } else if (portType.startsWith('branch_')) {
 926 |                     const cIdx = parseInt(portType.split('_')[1]) || 0
 927 |                     startPt = { x: sourceNode.position.x + sourceNode.w, y: sourceNode.position.y + getBranchPortCenterY(sourceNode, cIdx) }
 928 |                 } else {
 929 |                     const startOffsetY = sourceNode.node_type === 'branch' ? (sourceNode.h - 18) : (sourceNode.h / 2)
 930 |                     startPt = { x: sourceNode.position.x + sourceNode.w, y: sourceNode.position.y + startOffsetY }
 931 |                 }
 932 | 
 933 |                 const mousePt = { x: drawingConnection.value.currentX, y: drawingConnection.value.currentY }
 934 | 
 935 |                 let safeStartY = startPt.y
 936 |                 if (portType === 'succ') {
 937 |                     safeStartY = Math.max(startPt.y + 20, mousePt.y)
 938 |                 }
 939 | 
 940 |                 const rawPoints = [
 941 |                     startPt,
 942 |                     { x: startPt.x, y: safeStartY },
 943 |                     { x: mousePt.x, y: safeStartY },
 944 |                     mousePt
 945 |                 ]
 946 | 
 947 |                 const pathStr = getRoundedPathString(rawPoints, 10)
 948 |                 const arrowDir = getArrowDirection(rawPoints)
 949 |                 drawingConnection.value.previewMarkerUrl = `url(#arrow-${portType === 'fail' ? 'fail' : 'succ'}-${arrowDir})`
 950 | 
 951 |                 edges.push({
 952 |                     id: 'temp_drawing',
 953 |                     path: pathStr,
 954 |                     label: '',
 955 |                     isFail: portType === 'fail',
 956 |                     markerUrl: drawingConnection.value.previewMarkerUrl,
 957 |                     selected: false,
 958 |                     labelX: 0,
 959 |                     labelY: 0,
 960 |                     gridPoints: [],
 961 |                     rawPixelPoints: rawPoints
 962 |                 })
 963 |             }
 964 |         }
 965 | 
 966 |         return edges
 967 |     })
 968 | 
 969 |     const drawMinimap = () => {
 970 |         const canvas = minimapCanvasRef.value
 971 |         if (!canvas || !containerRef.value) return
 972 |         const ctx = canvas.getContext('2d')
 973 |         const mapW = canvas.width
 974 |         const mapH = canvas.height
 975 | 
 976 |         ctx.clearRect(0, 0, mapW, mapH)
 977 |         ctx.fillStyle = '#1e1f29'
 978 |         ctx.fillRect(0, 0, mapW, mapH)
 979 | 
 980 |         const nodes = renderNodes.value
 981 |         const groups = dynamicGroups.value
 982 |         if (!nodes.length && !groups.length) return
 983 | 
 984 |         let minX = -1000, minY = -1000, maxX = 3000, maxY = 3000
 985 |         nodes.forEach(n => {
 986 |             minX = Math.min(minX, n.position.x - 200)
 987 |             minY = Math.min(minY, n.position.y - 200)
 988 |             maxX = Math.max(maxX, n.position.x + n.w + 200)
 989 |             maxY = Math.max(maxY, n.position.y + n.h + 200)
 990 |         })
 991 | 
 992 |         const worldW = maxX - minX
 993 |         const worldH = maxY - minY
 994 |         const scaleX = mapW / worldW
 995 |         const scaleY = mapH / worldH
 996 |         const mapScale = Math.min(scaleX, scaleY)
 997 | 
 998 |         const toMapCoord = (wx, wy) => ({
 999 |             x: (wx - minX) * mapScale + (mapW - worldW * mapScale) / 2,
1000 |             y: (wy - minY) * mapScale + (mapH - worldH * mapScale) / 2
1001 |         })
1002 | 
1003 |         ctx.strokeStyle = '#4ed19c33'
1004 |         ctx.lineWidth = 1
1005 |         groups.forEach(g => {
1006 |             const p = toMapCoord(g.box.x, g.box.y)
1007 |             ctx.strokeRect(p.x, p.y, g.box.w * mapScale, g.box.h * mapScale)
1008 |         })
1009 | 
1010 |         nodes.forEach(n => {
1011 |             const p = toMapCoord(n.position.x, n.position.y)
1012 |             ctx.fillStyle = n.selected ? '#409EFF' : '#4ed19c'
1013 |             ctx.fillRect(p.x, p.y, Math.max(4, n.w * mapScale), Math.max(3, n.h * mapScale))
1014 |         })
1015 | 
1016 |         const containerW = containerRef.value.clientWidth
1017 |         const containerH = containerRef.value.clientHeight
1018 |         const viewLeft = -viewport.value.x / viewport.value.zoom
1019 |         const viewTop = -viewport.value.y / viewport.value.zoom
1020 |         const viewW = containerW / viewport.value.zoom
1021 |         const viewH = containerH / viewport.value.zoom
1022 | 
1023 |         const vpCoord = toMapCoord(viewLeft, viewTop)
1024 |         ctx.strokeStyle = '#409EFF'
1025 |         ctx.lineWidth = 1.5
1026 |         ctx.strokeRect(vpCoord.x, vpCoord.y, viewW * mapScale, viewH * mapScale)
1027 |         ctx.fillStyle = 'rgba(64, 158, 255, 0.1)'
1028 |         ctx.fillRect(vpCoord.x, vpCoord.y, viewW * mapScale, viewH * mapScale)
1029 |     }
1030 | 
1031 |     const onMinimapClick = (e) => {
1032 |         const canvas = minimapCanvasRef.value
1033 |         if (!canvas || !containerRef.value) return
1034 |         const rect = canvas.getBoundingClientRect()
1035 |         const clickX = e.clientX - rect.left
1036 |         const clickY = e.clientY - rect.top
1037 | 
1038 |         const nodes = renderNodes.value
1039 |         let minX = -1000, minY = -1000, maxX = 3000, maxY = 3000
1040 |         nodes.forEach(n => {
1041 |             minX = Math.min(minX, n.position.x - 200)
1042 |             minY = Math.min(minY, n.position.y - 200)
1043 |             maxX = Math.max(maxX, n.position.x + n.w + 200)
1044 |             maxY = Math.max(maxY, n.position.y + n.h + 200)
1045 |         })
1046 | 
1047 |         const worldW = maxX - minX
1048 |         const worldH = maxY - minY
1049 |         const mapScale = Math.min(canvas.width / worldW, canvas.height / worldH)
1050 | 
1051 |         const targetWorldX = (clickX - (canvas.width - worldW * mapScale) / 2) / mapScale + minX
1052 |         const targetWorldY = (clickY - (canvas.height - worldH * mapScale) / 2) / mapScale + minY
1053 | 
1054 |         const containerW = containerRef.value.clientWidth
1055 |         const containerH = containerRef.value.clientHeight
1056 | 
1057 |         viewport.value.x = -(targetWorldX - containerW / (2 * viewport.value.zoom)) * viewport.value.zoom
1058 |         viewport.value.y = -(targetWorldY - containerH / (2 * viewport.value.zoom)) * viewport.value.zoom
1059 |         drawMinimap()
1060 |     }
1061 | 
1062 |     watch([renderNodes, dynamicGroups, viewport], () => {
1063 |         nextTick(drawMinimap)
1064 |     }, { deep: true })
1065 | 
1066 |     watch(() => store.minimapExpanded, (val) => {
1067 |         if (val) {
1068 |             nextTick(drawMinimap)
1069 |         }
1070 |     })
1071 | 
1072 |     const onCanvasMouseDown = (e) => {
1073 |         customContextMenu.visible = false
1074 | 
1075 |         const isBlankArea = e.target === containerRef.value ||
1076 |             e.target.classList.contains('canvas-viewport') ||
1077 |             e.target.tagName === 'svg' ||
1078 |             e.target.classList.contains('canvas-edges-layer')
1079 | 
1080 |         if (isBlankArea) {
1081 |             if (e.shiftKey && e.button === 0) {
1082 |                 spawnMenu.value = {
1083 |                     visible: true,
1084 |                     x: e.clientX,
1085 |                     y: e.clientY,
1086 |                     sourceNodeId: null,
1087 |                     portType: 'succ',
1088 |                     clientX: e.clientX,
1089 |                     clientY: e.clientY
1090 |                 }
1091 |                 e.stopPropagation()
1092 |                 return
1093 |             }
1094 | 
1095 |             localSelectedNodeIds.value = []
1096 |             store.selectedNodeIds = []
1097 |             store.selectedGroupId = null
1098 |             selectedEdgeId.value = null
1099 |         }
1100 | 
1101 |         if (e.altKey) {
1102 |             selectionBox.value = { visible: true, startX: e.clientX, startY: e.clientY, endX: e.clientX, endY: e.clientY }
1103 |         } else {
1104 |             isPanning.value = true
1105 |             panStart.value = { x: e.clientX - viewport.value.x, y: e.clientY - viewport.value.y }
1106 |         }
1107 |         spawnMenu.value.visible = false
1108 |     }
1109 | 
1110 |     const onNodeMouseDown = (e, node) => {
1111 |         isCtrlHeldRef.value = e.ctrlKey
1112 | 
1113 |         draggedSourceGroupSnapshot.value = null
1114 |         ghostPlaceholder.value = null
1115 | 
1116 |         ghostPlaceholder.value = {
1117 |             node_id: `ghost_${node.node_id}`,
1118 |             position: { ...node.position },
1119 |             w: NODE_GRID_W * GRID_SIZE,
1120 |             h: node.h || 120
1121 |         }
1122 | 
1123 |         const tasks = store.blueprint?.tasks || []
1124 |         tasks.forEach((t, tIdx) => {
1125 |             const found = (t.nodes || []).find(n => n.node_id === node.node_id)
1126 |             if (found) {
1127 |                 const groupInfo = dynamicGroups.value[tIdx]
1128 |                 if (groupInfo && groupInfo.box) {
1129 |                     draggedSourceGroupSnapshot.value = { ...groupInfo.box }
1130 |                 }
1131 |             }
1132 |         })
1133 | 
1134 |         if (e.ctrlKey) {
1135 |             if (localSelectedNodeIds.value.includes(node.node_id)) {
1136 |                 localSelectedNodeIds.value = localSelectedNodeIds.value.filter(id => id !== node.node_id)
1137 |             } else {
1138 |                 localSelectedNodeIds.value.push(node.node_id)
1139 |             }
1140 |         } else {
1141 |             if (!localSelectedNodeIds.value.includes(node.node_id)) {
1142 |                 localSelectedNodeIds.value = [node.node_id]
1143 |             }
1144 |         }
1145 | 
1146 |         store.selectedNodeIds = [...localSelectedNodeIds.value]
1147 |         store.selectedGroupId = null
1148 | 
1149 |         draggingNodeId.value = node.node_id
1150 |         dragStartMouse.value = { x: e.clientX, y: e.clientY }
1151 |         nodeInitialPos.value = node.position ? { ...node.position } : { x: 0, y: 0 }
1152 |         hasMoved.value = false
1153 |         e.stopPropagation()
1154 |     }
1155 | 
1156 |     const onGlobalMouseMove = (e) => {
1157 |         isCtrlHeldRef.value = e.ctrlKey
1158 | 
1159 |         if (isPanning.value) {
1160 |             viewport.value.x = e.clientX - panStart.value.x
1161 |             viewport.value.y = e.clientY - panStart.value.y
1162 |         } else if (selectionBox.value.visible) {
1163 |             selectionBox.value.endX = e.clientX
1164 |             selectionBox.value.endY = e.clientY
1165 |         } else if (draggingNodeId.value) {
1166 |             const dist = Math.hypot(e.clientX - dragStartMouse.value.x, e.clientY - dragStartMouse.value.y)
1167 |             if (dist > 6) {
1168 |                 hasMoved.value = true
1169 |             }
1170 | 
1171 |             if (hasMoved.value) {
1172 |                 const dx = (e.clientX - dragStartMouse.value.x) / viewport.value.zoom
1173 |                 const dy = (e.clientY - dragStartMouse.value.y) / viewport.value.zoom
1174 | 
1175 |                 const rawX = nodeInitialPos.value.x + dx
1176 |                 const rawY = nodeInitialPos.value.y + dy
1177 | 
1178 |                 localDraftPositions[draggingNodeId.value] = { x: rawX, y: rawY }
1179 | 
1180 |                 const MIN_GAP = 2 * GRID_SIZE
1181 | 
1182 |                 const currentDraggingNode = renderNodes.value.find(n => n.node_id === draggingNodeId.value)
1183 |                 const nodeW = currentDraggingNode?.w || (NODE_GRID_W * GRID_SIZE)
1184 |                 const nodeH = currentDraggingNode?.h || 120
1185 | 
1186 |                 const previewX = rawX - MIN_GAP
1187 |                 const previewY = rawY - MIN_GAP
1188 |                 const previewW = nodeW + MIN_GAP * 2
1189 |                 const previewH = nodeH + MIN_GAP * 2
1190 | 
1191 |                 let isColliding = false
1192 |                 const currentBox = {
1193 |                     minX: rawX,
1194 |                     maxX: rawX + nodeW,
1195 |                     minY: rawY,
1196 |                     maxY: rawY + nodeH
1197 |                 }
1198 | 
1199 |                 for (const otherNode of renderNodes.value) {
1200 |                     if (otherNode.node_id === draggingNodeId.value) continue
1201 |                     const otherPos = localDraftPositions[otherNode.node_id] || otherNode.position || { x: 0, y: 0 }
1202 |                     const otherSize = { w: otherNode.w || nodeW, h: otherNode.h || 120 }
1203 | 
1204 |                     const expandedOtherBox = {
1205 |                         minX: otherPos.x - MIN_GAP,
1206 |                         maxX: otherPos.x + otherSize.w + MIN_GAP,
1207 |                         minY: otherPos.y - MIN_GAP,
1208 |                         maxY: otherPos.y + otherSize.h + MIN_GAP
1209 |                     }
1210 | 
1211 |                     const isIntersect = !(
1212 |                         currentBox.maxX <= expandedOtherBox.minX ||
1213 |                         currentBox.minX >= expandedOtherBox.maxX ||
1214 |                         currentBox.maxY <= expandedOtherBox.minY ||
1215 |                         currentBox.minY >= expandedOtherBox.maxY
1216 |                     )
1217 | 
1218 |                     if (isIntersect) {
1219 |                         isColliding = true
1220 |                         break
1221 |                     }
1222 |                 }
1223 | 
1224 |                 dragPreviewBox.value = {
1225 |                     visible: true,
1226 |                     x: previewX,
1227 |                     y: previewY,
1228 |                     w: previewW,
1229 |                     h: previewH,
1230 |                     hasCollision: isColliding
1231 |                 }
1232 |             }
1233 |         } else if (drawingConnection.value.active && containerRef.value) {
1234 |             const rect = containerRef.value.getBoundingClientRect()
1235 |             const clientX = e.clientX - rect.left
1236 |             const clientY = e.clientY - rect.top
1237 |             const rawX = (clientX - viewport.value.x) / viewport.value.zoom
1238 |             const rawY = (clientY - viewport.value.y) / viewport.value.zoom
1239 |             drawingConnection.value.currentX = Math.round(rawX / GRID_SIZE) * GRID_SIZE
1240 |             drawingConnection.value.currentY = Math.round(rawY / GRID_SIZE) * GRID_SIZE
1241 |         }
1242 |     }
1243 | 
1244 |     const resolveCollisionsAndPushOthers = (targetNodeId, dropPos, allNodes, nodeSize) => {
1245 |         const GAP_GRIDS = 2
1246 | 
1247 |         let movingNodes = [{ id: targetNodeId, pos: { ...dropPos }, h: nodeSize.h, w: nodeSize.w }]
1248 |         localDraftPositions[targetNodeId] = { ...dropPos }
1249 | 
1250 |         let maxIterations = 15
1251 |         let iteration = 0
1252 | 
1253 |         while (iteration < maxIterations) {
1254 |             iteration++
1255 |             let hasNewCollision = false
1256 | 
1257 |             for (let i = 0; i < movingNodes.length; i++) {
1258 |                 const current = movingNodes[i]
1259 |                 const currPos = current.pos
1260 |                 const currSize = { w: current.w || nodeSize.w, h: current.h || nodeSize.h }
1261 | 
1262 |                 for (const other of allNodes) {
1263 |                     if (other.node_id === current.id) continue
1264 |                     if (movingNodes.some(m => m.id === other.node_id)) continue
1265 |                     if (ghostPlaceholder.value && other.node_id === ghostPlaceholder.value.node_id) continue
1266 | 
1267 |                     const alreadyMoved = movingNodes.find(m => m.id === other.node_id)
1268 |                     const otherPos = alreadyMoved ? alreadyMoved.pos : (localDraftPositions[other.node_id] || other.position)
1269 |                     const otherSize = {
1270 |                         w: other.w || nodeSize.w,
1271 |                         h: alreadyMoved ? alreadyMoved.h : (other.h || 120)
1272 |                     }
1273 | 
1274 |                     const isIntersect = !(
1275 |                         currPos.x + currSize.w + 40 <= otherPos.x ||
1276 |                         currPos.x >= otherPos.x + otherSize.w + 40 ||
1277 |                         currPos.y + currSize.h + 40 <= otherPos.y ||
1278 |                         currPos.y >= otherPos.y + otherSize.h + 40
1279 |                     )
1280 | 
1281 |                     if (isIntersect) {
1282 |                         hasNewCollision = true
1283 | 
1284 |                         const currCenterX = currPos.x + currSize.w / 2
1285 |                         const otherCenterX = otherPos.x + otherSize.w / 2
1286 |                         const currCenterY = currPos.y + currSize.h / 2
1287 |                         const otherCenterY = otherPos.y + otherSize.h / 2
1288 | 
1289 |                         const dx = currCenterX - otherCenterX
1290 |                         const dy = currCenterY - otherCenterY
1291 | 
1292 |                         let nextPos = { ...otherPos }
1293 | 
1294 |                         if (Math.abs(dx) > Math.abs(dy)) {
1295 |                             if (dx < 0) {
1296 |                                 const overlapPx = (currPos.x + currSize.w) - otherPos.x
1297 |                                 const overlapGrids = Math.ceil(overlapPx / GRID_SIZE)
1298 |                                 nextPos.x = otherPos.x + (overlapGrids + GAP_GRIDS) * GRID_SIZE
1299 |                             } else {
1300 |                                 const overlapPx = (otherPos.x + otherSize.w) - currPos.x
1301 |                                 const overlapGrids = Math.ceil(overlapPx / GRID_SIZE)
1302 |                                 nextPos.x = otherPos.x - (overlapGrids + GAP_GRIDS) * GRID_SIZE
1303 |                             }
1304 |                         } else {
1305 |                             if (dy < 0) {
1306 |                                 const overlapPx = (currPos.y + currSize.h) - otherPos.y
1307 |                                 const overlapGrids = Math.ceil(overlapPx / GRID_SIZE)
1308 |                                 nextPos.y = otherPos.y + (overlapGrids + GAP_GRIDS) * GRID_SIZE
1309 |                             } else {
1310 |                                 const overlapPx = (otherPos.y + otherSize.h) - currPos.y
1311 |                                 const overlapGrids = Math.ceil(overlapPx / GRID_SIZE)
1312 |                                 nextPos.y = otherPos.y - (overlapGrids + GAP_GRIDS) * GRID_SIZE
1313 |                             }
1314 |                         }
1315 | 
1316 |                         nextPos.x = Math.round(nextPos.x / GRID_SIZE) * GRID_SIZE
1317 |                         nextPos.y = Math.round(nextPos.y / GRID_SIZE) * GRID_SIZE
1318 | 
1319 |                         localDraftPositions[other.node_id] = nextPos
1320 |                         other.position = nextPos
1321 | 
1322 |                         movingNodes.push({
1323 |                             id: other.node_id,
1324 |                             pos: nextPos,
1325 |                             h: otherSize.h,
1326 |                             w: otherSize.w
1327 |                         })
1328 |                     }
1329 |                 }
1330 |             }
1331 |             if (!hasNewCollision) break
1332 |         }
1333 |         return localDraftPositions[targetNodeId] || dropPos
1334 |     }
1335 | 
1336 |     const calculateOverlapRatio = (rectA, rectB) => {
1337 |         if (!rectA || !rectB) return 0
1338 |         const xOverlap = Math.max(0, Math.min(rectA.x + rectA.w, rectB.x + rectB.w) - Math.max(rectA.x, rectB.x))
1339 |         const yOverlap = Math.max(0, Math.min(rectA.y + rectA.h, rectB.y + rectB.h) - Math.max(rectA.y, rectB.y))
1340 |         const intersectionArea = xOverlap * yOverlap
1341 |         const areaA = rectA.w * rectA.h
1342 |         if (areaA <= 0) return 0
1343 |         return intersectionArea / areaA
1344 |     }
1345 | 
1346 |     const resolveGroupCollisionsAndPushOthers = (draggingTaskId, newBox, allGroups) => {
1347 |         const MIN_GROUP_GAP = GRID_SIZE
1348 |         let movingGroups = [{ id: draggingTaskId, box: { ...newBox } }]
1349 |         let adjustedBoxes = { [draggingTaskId]: { ...newBox } }
1350 | 
1351 |         let maxIterations = 10
1352 |         let iteration = 0
1353 | 
1354 |         while (iteration < maxIterations) {
1355 |             iteration++
1356 |             let hasNewCollision = false
1357 | 
1358 |             for (let i = 0; i < movingGroups.length; i++) {
1359 |                 const current = movingGroups[i]
1360 |                 const currBox = current.box
1361 | 
1362 |                 for (const other of allGroups) {
1363 |                     if (other.taskId === current.id) continue
1364 |                     if (movingGroups.some(m => m.id === other.taskId)) continue
1365 | 
1366 |                     const otherBox = adjustedBoxes[other.taskId] || other.box
1367 | 
1368 |                     const isIntersect = !(
1369 |                         currBox.x + currBox.w + MIN_GROUP_GAP <= otherBox.x ||
1370 |                         currBox.x >= otherBox.x + otherBox.w + MIN_GROUP_GAP ||
1371 |                         currBox.y + currBox.h + MIN_GROUP_GAP <= otherBox.y ||
1372 |                         currBox.y >= otherBox.y + otherBox.h + MIN_GROUP_GAP
1373 |                     )
1374 | 
1375 |                     if (isIntersect) {
1376 |                         hasNewCollision = true
1377 | 
1378 |                         const currCenterX = currBox.x + currBox.w / 2
1379 |                         const otherCenterX = otherBox.x + otherBox.w / 2
1380 |                         const currCenterY = currBox.y + currBox.h / 2
1381 |                         const otherCenterY = otherBox.y + otherBox.h / 2
1382 | 
1383 |                         const dx = otherCenterX - currCenterX
1384 |                         const dy = otherCenterY - currCenterY
1385 | 
1386 |                         const overlapX = Math.min(currBox.x + currBox.w + MIN_GROUP_GAP - otherBox.x, otherBox.x + otherBox.w + MIN_GROUP_GAP - currBox.x)
1387 |                         const overlapY = Math.min(currBox.y + currBox.h + MIN_GROUP_GAP - otherBox.y, otherBox.y + otherBox.h + MIN_GROUP_GAP - currBox.y)
1388 | 
1389 |                         let nextBox = { ...otherBox }
1390 | 
1391 |                         if (overlapX < overlapY) {
1392 |                             if (dx > 0) {
1393 |                                 nextBox.x = currBox.x + currBox.w + MIN_GROUP_GAP
1394 |                             } else {
1395 |                                 nextBox.x = currBox.x - otherBox.w - MIN_GROUP_GAP
1396 |                             }
1397 |                         } else {
1398 |                             if (dy > 0) {
1399 |                                 nextBox.y = currBox.y + currBox.h + MIN_GROUP_GAP
1400 |                             } else {
1401 |                                 nextBox.y = currBox.y - otherBox.h - MIN_GROUP_GAP
1402 |                             }
1403 |                         }
1404 | 
1405 |                         nextBox.x = Math.round(nextBox.x / GRID_SIZE) * GRID_SIZE
1406 |                         nextBox.y = Math.round(nextBox.y / GRID_SIZE) * GRID_SIZE
1407 | 
1408 |                         adjustedBoxes[other.taskId] = nextBox
1409 |                         movingGroups.push({ id: other.taskId, box: nextBox })
1410 |                     }
1411 |                 }
1412 |             }
1413 |             if (!hasNewCollision) break
1414 |         }
1415 |         return adjustedBoxes
1416 |     }
1417 | 
1418 |     const onGlobalMouseUp = async (e) => {
1419 |         isPanning.value = false
1420 | 
1421 |         if (selectionBox.value.visible) {
1422 |             selectionBox.value.visible = false
1423 |         }
1424 | 
1425 |         dragPreviewBox.value.visible = false
1426 | 
1427 |         const wasDrawing = drawingConnection.value.active
1428 |         const sourceId = drawingConnection.value.sourceNodeId
1429 |         const portType = drawingConnection.value.portType
1430 |         drawingConnection.value.active = false
1431 | 
1432 |         if (draggingNodeId.value) {
1433 |             const nodeId = draggingNodeId.value
1434 |             const isCtrlHeld = isCtrlHeldRef.value || e.ctrlKey
1435 |             draggingNodeId.value = false
1436 |             isCtrlHeldRef.value = false
1437 | 
1438 |             if (hasMoved.value) {
1439 |                 const rawPos = localDraftPositions[nodeId] || nodeInitialPos.value
1440 |                 const finalPos = {
1441 |                     x: Math.round(rawPos.x / GRID_SIZE) * GRID_SIZE,
1442 |                     y: Math.round(rawPos.y / GRID_SIZE) * GRID_SIZE
1443 |                 }
1444 | 
1445 |                 const tasks = store.blueprint?.tasks || []
1446 |                 const targetNodeObj = renderNodes.value.find(n => n.node_id === nodeId)
1447 |                 const currentNodeSize = { w: targetNodeObj?.w || (NODE_GRID_W * GRID_SIZE), h: targetNodeObj?.h || 120 }
1448 | 
1449 |                 let targetTaskIndex = -1
1450 |                 let isCreatingNewGroup = false
1451 | 
1452 |                 if (isCtrlHeld && draggedSourceGroupSnapshot.value) {
1453 |                     const nodeRectBeforePush = { x: finalPos.x, y: finalPos.y, w: currentNodeSize.w, h: currentNodeSize.h }
1454 |                     const overlapWithSnapshot = calculateOverlapRatio(nodeRectBeforePush, draggedSourceGroupSnapshot.value)
1455 | 
1456 |                     if (overlapWithSnapshot === 0) {
1457 |                         dynamicGroups.value.forEach((g, gIdx) => {
1458 |                             let currentSourceTIdx = -1
1459 |                             tasks.forEach((t, tI) => {
1460 |                                 if ((t.nodes || []).some(n => n.node_id === nodeId)) currentSourceTIdx = tI
1461 |                             })
1462 |                             if (gIdx === currentSourceTIdx) return
1463 | 
1464 |                             const ratio = calculateOverlapRatio(nodeRectBeforePush, g.box)
1465 |                             if (ratio >= 1.0) {
1466 |                                 targetTaskIndex = gIdx
1467 |                             }
1468 |                         })
1469 | 
1470 |                         if (targetTaskIndex === -1) {
1471 |                             isCreatingNewGroup = true
1472 |                         }
1473 |                     }
1474 |                 }
1475 | 
1476 |                 const safePos = resolveCollisionsAndPushOthers(nodeId, finalPos, renderNodes.value, currentNodeSize)
1477 | 
1478 |                 let sourceTaskIndex = -1
1479 |                 let sourceNodeObj = null
1480 |                 tasks.forEach((t, tIdx) => {
1481 |                     const found = (t.nodes || []).find(n => n.node_id === nodeId)
1482 |                     if (found) {
1483 |                         sourceTaskIndex = tIdx
1484 |                         sourceNodeObj = found
1485 |                     }
1486 |                 })
1487 | 
1488 |                 if (sourceTaskIndex !== -1 && isCtrlHeld && draggedSourceGroupSnapshot.value) {
1489 |                     const originalTask = tasks[sourceTaskIndex]
1490 |                     const nodeRectAfterPush = { x: safePos.x, y: safePos.y, w: currentNodeSize.w, h: currentNodeSize.h }
1491 |                     const overlapWithSnapshot = calculateOverlapRatio(nodeRectAfterPush, draggedSourceGroupSnapshot.value)
1492 | 
1493 |                     if (overlapWithSnapshot === 0) {
1494 |                         originalTask.nodes = (originalTask.nodes || []).filter(n => n.node_id !== nodeId)
1495 |                         sourceNodeObj.position = safePos
1496 | 
1497 |                         if (targetTaskIndex !== -1) {
1498 |                             const targetTask = tasks[targetTaskIndex]
1499 |                             if (!targetTask.nodes) targetTask.nodes = []
1500 |                             targetTask.nodes.push(sourceNodeObj)
1501 |                             ElMessage.success(`节点已被纳入组 [${targetTask.task_name}]`)
1502 |                         } else if (isCreatingNewGroup) {
1503 |                             const newTaskId = `task_${Date.now()}`
1504 |                             const newTask = {
1505 |                                 task_id: newTaskId,
1506 |                                 task_name: '新建组',
1507 |                                 loop_count: 1,
1508 |                                 loop_interval: 0,
1509 |                                 nodes: [sourceNodeObj]
1510 |                             }
1511 |                             tasks.push(newTask)
1512 |                             ElMessage.success('节点已成功脱离，并自动创建放入【新建组】')
1513 |                         }
1514 |                     } else {
1515 |                         sourceNodeObj.position = safePos
1516 |                     }
1517 |                 } else {
1518 |                     for (const task of tasks) {
1519 |                         const found = (task.nodes || []).find(n => n.node_id === nodeId)
1520 |                         if (found) {
1521 |                             found.position = safePos
1522 |                             break
1523 |                         }
1524 |                     }
1525 |                 }
1526 | 
1527 |                 tasks.forEach(t => {
1528 |                     (t.nodes || []).forEach(n => {
1529 |                         if (localDraftPositions[n.node_id]) {
1530 |                             n.position = localDraftPositions[n.node_id]
1531 |                             delete localDraftPositions[n.node_id]
1532 |                         }
1533 |                     })
1534 |                 })
1535 | 
1536 |                 await nextTick()
1537 |                 const currentGroupsForCheck = dynamicGroups.value.map(g => ({
1538 |                     taskId: g.taskId,
1539 |                     box: { x: g.box.x, y: g.box.y, w: g.box.w, h: g.box.h }
1540 |                 }))
1541 | 
1542 |                 let globalAdjustedBoxes = {}
1543 |                 let activeTaskObj = tasks[sourceTaskIndex] || tasks[tasks.length - 1]
1544 |                 if (activeTaskObj) {
1545 |                     const activeGroupId = activeTaskObj.task_id
1546 |                     const activeGroupInfo = currentGroupsForCheck.find(x => x.taskId === activeGroupId)
1547 | 
1548 |                     if (activeGroupInfo) {
1549 |                         const others = currentGroupsForCheck.filter(x => x.taskId !== activeGroupId)
1550 |                         globalAdjustedBoxes = resolveGroupCollisionsAndPushOthers(activeGroupId, activeGroupInfo.box, others)
1551 |                     }
1552 |                 }
1553 | 
1554 |                 tasks.forEach(t => {
1555 |                     const newBox = globalAdjustedBoxes[t.task_id]
1556 |                     const oldGroup = currentGroupsForCheck.find(x => x.taskId === t.task_id)
1557 |                     if (newBox && oldGroup && oldGroup.box) {
1558 |                         const shiftX = (Number(newBox.x) || 0) - (Number(oldGroup.box.x) || 0)
1559 |                         const shiftY = (Number(newBox.y) || 0) - (Number(oldGroup.box.y) || 0)
1560 | 
1561 |                         if (shiftX !== 0 || shiftY !== 0) {
1562 |                             (t.nodes || []).forEach(n => {
1563 |                                 n.position.x = Math.round((n.position.x + shiftX) / GRID_SIZE) * GRID_SIZE
1564 |                                 n.position.y = Math.round((n.position.y + shiftY) / GRID_SIZE) * GRID_SIZE
1565 |                             })
1566 |                         }
1567 |                     }
1568 |                 })
1569 | 
1570 |                 store.blueprint.tasks = tasks.filter(t => (t.nodes || []).length > 0)
1571 |                 await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)
1572 | 
1573 |                 draggedSourceGroupSnapshot.value = null
1574 |                 ghostPlaceholder.value = null
1575 |                 delete localDraftPositions[nodeId]
1576 | 
1577 |                 ElMessage.success('节点排版及组归属更新成功')
1578 |             }
1579 |             hasMoved.value = false
1580 |         }
1581 | 
1582 |         // ⚡ 拖拽空放断开原有连线
1583 |         if (wasDrawing) {
1584 |             const tasks = store.blueprint?.tasks || []
1585 |             if (tasks.length === 0) return
1586 | 
1587 |             let sourceNodeObj = null
1588 |             for (const t of tasks) {
1589 |                 const found = (t.nodes || []).find(n => n.node_id === sourceId)
1590 |                 if (found) { sourceNodeObj = found; break }
1591 |             }
1592 | 
1593 |             if (sourceNodeObj) {
1594 |                 let hasExisting = false
1595 | 
1596 |                 if (portType.startsWith('branch_')) {
1597 |                     const cIdx = parseInt(portType.split('_')[1]) || 0
1598 |                     if (sourceNodeObj.params?.candidates?.[cIdx]?.on_success?.target_node) {
1599 |                         hasExisting = true
1600 |                         sourceNodeObj.params.candidates[cIdx].on_success = {}
1601 |                     }
1602 |                 } else if (portType === 'fail' && sourceNodeObj.params?.on_failure?.target_node) {
1603 |                     hasExisting = true
1604 |                     sourceNodeObj.params.on_failure = {}
1605 |                 } else if (portType === 'succ' && sourceNodeObj.params?.on_success?.target_node) {
1606 |                     hasExisting = true
1607 |                     sourceNodeObj.params.on_success = {}
1608 |                 }
1609 | 
1610 |                 if (hasExisting) {
1611 |                     try {
1612 |                         await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)
1613 |                         ElMessage.success('已成功断开连线')
1614 |                     } catch (err) {
1615 |                         console.error('断线保存失败:', err)
1616 |                         ElMessage.error('断线保存失败')
1617 |                     }
1618 |                     return
1619 |                 }
1620 |             }
1621 | 
1622 |             spawnMenu.value = {
1623 |                 visible: true,
1624 |                 x: e.clientX,
1625 |                 y: e.clientY,
1626 |                 sourceNodeId: sourceId,
1627 |                 portType,
1628 |                 clientX: e.clientX,
1629 |                 clientY: e.clientY
1630 |             }
1631 |         }
1632 |     }
1633 | 
1634 |     const onCanvasWheel = (e) => {
1635 |         e.preventDefault()
1636 |         if (!containerRef.value) return
1637 | 
1638 |         const rect = containerRef.value.getBoundingClientRect()
1639 |         const mouseX = e.clientX - rect.left
1640 |         const mouseY = e.clientY - rect.top
1641 | 
1642 |         const oldZoom = viewport.value.zoom
1643 |         const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9
1644 |         const newZoom = Math.min(Math.max(oldZoom * zoomFactor, 0.2), 4)
1645 | 
1646 |         if (newZoom === oldZoom) return
1647 | 
1648 |         const worldX = (mouseX - viewport.value.x) / oldZoom
1649 |         const worldY = (mouseY - viewport.value.y) / oldZoom
1650 | 
1651 |         viewport.value.zoom = newZoom
1652 |         viewport.value.x = mouseX - worldX * newZoom
1653 |         viewport.value.y = mouseY - worldY * newZoom
1654 | 
1655 |         if (typeof drawMinimap === 'function') {
1656 |             drawMinimap()
1657 |         }
1658 |     }
1659 | 
1660 |     watch(() => store.focusTarget, (target) => {
1661 |         if (!target || !containerRef.value) return
1662 |         const containerW = containerRef.value.clientWidth
1663 |         const containerH = containerRef.value.clientHeight
1664 |         let targetX = 0
1665 |         let targetY = 0
1666 | 
1667 |         if (target.type === 'node') {
1668 |             const node = renderNodes.value.find(n => n.node_id === target.id)
1669 |             if (node) {
1670 |                 targetX = node.position.x + node.w / 2
1671 |                 targetY = node.position.y + node.h / 2
1672 |             }
1673 |         } else if (target.type === 'group') {
1674 |             const group = dynamicGroups.value.find(g => g.groupId === target.id || g.taskId === target.id)
1675 |             if (group) {
1676 |                 targetX = group.box.x + group.box.w / 2
1677 |                 targetY = group.box.y + group.box.h / 2
1678 |             }
1679 |         }
1680 | 
1681 |         if (targetX !== 0 || targetY !== 0) {
1682 |             viewport.value.x = containerW / 2 - targetX * viewport.value.zoom
1683 |             viewport.value.y = containerH / 2 - targetY * viewport.value.zoom
1684 |             if (typeof drawMinimap === 'function') drawMinimap()
1685 |         }
1686 |     }, { deep: true })
1687 | 
1688 |     // ⚡ 释放鼠标确认建立 Branch 行级或通用连线
1689 |     const onNodeMouseUpCard = async (e, targetNode) => {
1690 |         if (drawingConnection.value.active) {
1691 |             const sourceId = drawingConnection.value.sourceNodeId
1692 |             const portType = drawingConnection.value.portType
1693 | 
1694 |             drawingConnection.value.active = false
1695 | 
1696 |             const tasks = store.blueprint?.tasks || []
1697 |             if (tasks.length === 0) {
1698 |                 ElMessage.warning('数据同步中，请稍候再试...')
1699 |                 e.stopPropagation()
1700 |                 return
1701 |             }
1702 | 
1703 |             if (sourceId && sourceId !== targetNode.node_id) {
1704 |                 let sourceNodeObj = null
1705 |                 let targetTaskFound = null
1706 | 
1707 |                 for (const t of tasks) {
1708 |                     const foundSource = (t.nodes || []).find(n => n.node_id === sourceId)
1709 |                     if (foundSource) sourceNodeObj = foundSource
1710 | 
1711 |                     const foundTarget = (t.nodes || []).find(n => n.node_id === targetNode.node_id)
1712 |                     if (foundTarget) targetTaskFound = t
1713 |                 }
1714 | 
1715 |                 if (sourceNodeObj) {
1716 |                     if (!sourceNodeObj.params) sourceNodeObj.params = {}
1717 | 
1718 |                     const connectionData = {
1719 |                         target_task: targetTaskFound ? targetTaskFound.task_id : '',
1720 |                         target_node: targetNode.node_id
1721 |                     }
1722 | 
1723 |                     if (portType.startsWith('branch_')) {
1724 |                         const cIdx = parseInt(portType.split('_')[1]) || 0
1725 |                         if (!sourceNodeObj.params.candidates) sourceNodeObj.params.candidates = []
1726 |                         if (sourceNodeObj.params.candidates[cIdx]) {
1727 |                             sourceNodeObj.params.candidates[cIdx].on_success = { ...connectionData }
1728 |                             ElMessage.success(`分支 ${cIdx + 1} 成功指向 ➔ [${targetNode.node_name}]`)
1729 |                         }
1730 |                     } else if (portType === 'fail') {
1731 |                         sourceNodeObj.params.on_failure = { ...connectionData }
1732 |                         ElMessage.success(`Else/失败分支指向 ➔ [${targetNode.node_name}]`)
1733 |                     } else {
1734 |                         sourceNodeObj.params.on_success = { ...connectionData }
1735 |                         ElMessage.success(`成功流向指向 ➔ [${targetNode.node_name}]`)
1736 |                     }
1737 | 
1738 |                     try {
1739 |                         await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)
1740 |                     } catch (saveErr) {
1741 |                         console.error('连线保存失败:', saveErr)
1742 |                         ElMessage.error('连线保存失败')
1743 |                     }
1744 |                 }
1745 |             }
1746 |             e.stopPropagation()
1747 |         }
1748 |     }
1749 | 
1750 |     const onNodeDoubleClick = (e, node) => {
1751 |         store.selectedNodeIds = [node.node_id]
1752 |         store.selectedGroupId = null
1753 |         localSelectedNodeIds.value = [node.node_id]
1754 |         e.stopPropagation()
1755 |     }
1756 | 
1757 |     const openGroupInspector = (e, group) => {
1758 |         store.selectedGroupId = group.groupId
1759 |         store.selectedNodeIds = []
1760 |         localSelectedNodeIds.value = []
1761 |         e.stopPropagation()
1762 |     }
1763 | 
1764 |     const startGroupDrag = (e, groupId) => {
1765 |         e.stopPropagation()
1766 |         const startX = e.clientX
1767 |         const startY = e.clientY
1768 |         let hasGroupMoved = false
1769 | 
1770 |         const tasks = store.blueprint?.tasks || []
1771 |         const taskIndex = tasks.findIndex((t, idx) => `group_${t.task_id || idx}` === groupId)
1772 |         if (taskIndex === -1) return
1773 | 
1774 |         const activeTask = tasks[taskIndex]
1775 |         const taskNodes = activeTask.nodes || []
1776 | 
1777 |         const initialNodePositions = {}
1778 |         tasks.forEach(t => {
1779 |             (t.nodes || []).forEach(n => {
1780 |                 initialNodePositions[n.node_id] = { x: n.position?.x || 0, y: n.position?.y || 0 }
1781 |             })
1782 |         })
1783 | 
1784 |         const currentGroupInfo = dynamicGroups.value.find(g => g.groupId === groupId)
1785 |         if (!currentGroupInfo) return
1786 |         const initialBox = { ...currentGroupInfo.box }
1787 | 
1788 |         const onMouseMove = (moveEvent) => {
1789 |             const dist = Math.hypot(moveEvent.clientX - startX, moveEvent.clientY - startY)
1790 |             if (dist > 6) {
1791 |                 hasGroupMoved = true
1792 |             }
1793 | 
1794 |             if (hasGroupMoved) {
1795 |                 const dx = (moveEvent.clientX - startX) / viewport.value.zoom
1796 |                 const dy = (moveEvent.clientY - startY) / viewport.value.zoom
1797 | 
1798 |                 taskNodes.forEach((n) => {
1799 |                     localDraftPositions[n.node_id] = {
1800 |                         x: initialNodePositions[n.node_id].x + dx,
1801 |                         y: initialNodePositions[n.node_id].y + dy
1802 |                     }
1803 |                 })
1804 |             }
1805 |         }
1806 | 
1807 |         const onMouseUp = async () => {
1808 |             window.removeEventListener('mousemove', onMouseMove)
1809 |             window.removeEventListener('mouseup', onMouseUp)
1810 | 
1811 |             if (!hasGroupMoved) return
1812 | 
1813 |             const finalDraftNode = taskNodes[0] ? (localDraftPositions[taskNodes[0].node_id] || taskNodes[0].position) : { x: 0, y: 0 }
1814 |             const initDraftNode = taskNodes[0] ? initialNodePositions[taskNodes[0].node_id] : { x: 0, y: 0 }
1815 |             const groupDx = (finalDraftNode.x - initDraftNode.x)
1816 |             const groupDy = (finalDraftNode.y - initDraftNode.y)
1817 | 
1818 |             const rawFinalBox = {
1819 |                 x: initialBox.x + groupDx,
1820 |                 y: initialBox.y + groupDy,
1821 |                 w: initialBox.w,
1822 |                 h: initialBox.h
1823 |             }
1824 |             const snappedFinalBox = {
1825 |                 x: Math.round(rawFinalBox.x / GRID_SIZE) * GRID_SIZE,
1826 |                 y: Math.round(rawFinalBox.y / GRID_SIZE) * GRID_SIZE,
1827 |                 w: rawFinalBox.w,
1828 |                 h: rawFinalBox.h
1829 |             }
1830 | 
1831 |             const allOtherGroups = dynamicGroups.value.map(g => ({
1832 |                 taskId: g.taskId,
1833 |                 box: g.box
1834 |             }))
1835 | 
1836 |             const adjustedBoxes = resolveGroupCollisionsAndPushOthers(activeTask.task_id, snappedFinalBox, allOtherGroups)
1837 | 
1838 |             tasks.forEach(t => {
1839 |                 const targetBox = adjustedBoxes[t.task_id]
1840 |                 const origGroup = dynamicGroups.value.find(g => g.taskId === t.task_id)
1841 |                 if (targetBox && origGroup && origGroup.box) {
1842 |                     let taskDeltaX = 0
1843 |                     let taskDeltaY = 0
1844 | 
1845 |                     if (t.task_id === activeTask.task_id) {
1846 |                         taskDeltaX = targetBox.x - initialBox.x
1847 |                         taskDeltaY = targetBox.y - initialBox.y
1848 |                     } else {
1849 |                         const origBox = origGroup.box
1850 |                         taskDeltaX = targetBox.x - origBox.x
1851 |                         taskDeltaY = targetBox.y - origBox.y
1852 |                     }
1853 | 
1854 |                     (t.nodes || []).forEach(n => {
1855 |                         const initPos = initialNodePositions[n.node_id]
1856 |                         if (initPos) {
1857 |                             const finalX = Math.round((initPos.x + taskDeltaX) / GRID_SIZE) * GRID_SIZE
1858 |                             const finalY = Math.round((initPos.y + taskDeltaY) / GRID_SIZE) * GRID_SIZE
1859 |                             n.position = { x: finalX, y: finalY }
1860 |                         }
1861 |                     })
1862 |                 }
1863 |                 (t.nodes || []).forEach(n => {
1864 |                     delete localDraftPositions[n.node_id]
1865 |                 })
1866 |             })
1867 | 
1868 |             store.blueprint.tasks = JSON.parse(JSON.stringify(tasks.filter(t => (t.nodes || []).length > 0)))
1869 | 
1870 |             try {
1871 |                 await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)
1872 |                 ElMessage.success('任务组移动及互斥排版保存成功')
1873 |             } catch (err) {
1874 |                 console.error('保存任务组位移失败', err)
1875 |                 ElMessage.error('保存任务组位移失败')
1876 |             }
1877 |         }
1878 | 
1879 |         window.addEventListener('mousemove', onMouseMove)
1880 |         window.addEventListener('mouseup', onMouseUp)
1881 |     }
1882 | 
1883 |     const startConnection = (e, nodeId, portType) => {
1884 |         if (!containerRef.value) return
1885 |         const rect = containerRef.value.getBoundingClientRect()
1886 |         const clientX = e.clientX - rect.left
1887 |         const clientY = e.clientY - rect.top
1888 | 
1889 |         drawingConnection.value = {
1890 |             active: true,
1891 |             sourceNodeId: nodeId,
1892 |             portType,
1893 |             currentX: (clientX - viewport.value.x) / viewport.value.zoom,
1894 |             currentY: (clientY - viewport.value.y) / viewport.value.zoom,
1895 |             previewMarkerUrl: 'url(#arrow-preview)'
1896 |         }
1897 |         e.stopPropagation()
1898 |     }
1899 | 
1900 |     const onEdgeClick = (edge) => {
1901 |         selectedEdgeId.value = edge.id
1902 |         ElMessage.info(`已选中连线`)
1903 |     }
1904 | 
1905 |     // ⚡ 快捷键删除选中连线（兼容 Branch 多分支出口）
1906 |     const globalKeydownHandler = async (e) => {
1907 |         if (e.key === 'Control') {
1908 |             isCtrlHeldRef.value = true
1909 |         }
1910 | 
1911 |         if ((e.key === 'Delete' || e.key === 'Backspace') && selectedEdgeId.value) {
1912 |             const edge = computedEdges.value.find(item => item.id === selectedEdgeId.value)
1913 |             if (edge) {
1914 |                 const tasks = store.blueprint?.tasks || []
1915 |                 let modified = false
1916 |                 for (const t of tasks) {
1917 |                     const foundNode = (t.nodes || []).find(n => n.node_id === edge.sourceNodeId)
1918 |                     if (foundNode) {
1919 |                         if (edge.typeFlag === 'branch' && foundNode.params?.candidates?.[edge.candIndex]) {
1920 |                             foundNode.params.candidates[edge.candIndex].on_success = {}
1921 |                             modified = true
1922 |                         } else if (edge.typeFlag === 'fail' && foundNode.params?.on_failure) {
1923 |                             foundNode.params.on_failure = {}
1924 |                             modified = true
1925 |                         } else if (edge.typeFlag === 'succ' && foundNode.params?.on_success) {
1926 |                             foundNode.params.on_success = {}
1927 |                             modified = true
1928 |                         }
1929 |                     }
1930 |                 }
1931 |                 if (modified) {
1932 |                     await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)
1933 |                     selectedEdgeId.value = null
1934 |                     ElMessage.success('已成功断开连线')
1935 |                 }
1936 |             }
1937 |         }
1938 |     }
1939 | 
1940 |     const globalKeyupHandler = (e) => {
1941 |         if (e.key === 'Control') {
1942 |             isCtrlHeldRef.value = false
1943 |         }
1944 |     }
1945 | 
1946 |     const createAndConnectNode = async (nodeType) => {
1947 |         try {
1948 |             const sourceId = spawnMenu.value.sourceNodeId
1949 |             const portType = spawnMenu.value.portType
1950 | 
1951 |             const targetClientX = spawnMenu.value.clientX || customContextMenu.clientX || window.innerWidth / 2
1952 |             const targetClientY = spawnMenu.value.clientY || customContextMenu.clientY || window.innerHeight / 2
1953 | 
1954 |             spawnMenu.value.visible = false
1955 |             customContextMenu.visible = false
1956 | 
1957 |             const tasks = store.blueprint?.tasks || []
1958 |             let targetTask = null, sourceNodeObj = null
1959 | 
1960 |             if (sourceId) {
1961 |                 for (const t of tasks) {
1962 |                     const found = (t.nodes || []).find(n => n.node_id === sourceId)
1963 |                     if (found) { targetTask = t; sourceNodeObj = found; break }
1964 |                 }
1965 |             } else {
1966 |                 const contextType = customContextMenu.targetType
1967 |                 const contextTaskId = customContextMenu.targetId
1968 | 
1969 |                 if (contextType === 'canvas_in_group' && contextTaskId) {
1970 |                     targetTask = tasks.find(t => t.task_id === contextTaskId)
1971 |                 }
1972 | 
1973 |                 if (!targetTask) {
1974 |                     const newTaskId = `task_${Date.now()}`
1975 |                     targetTask = {
1976 |                         task_id: newTaskId,
1977 |                         task_name: '新建组',
1978 |                         loop_count: 1,
1979 |                         loop_interval: 0,
1980 |                         nodes: []
1981 |                     }
1982 |                     tasks.push(targetTask)
1983 |                 }
1984 |             }
1985 | 
1986 |             if (!targetTask) return
1987 | 
1988 |             const newNodeId = `node_${Date.now()}`
1989 | 
1990 |             if (!targetTask.nodes) {
1991 |                 targetTask.nodes = []
1992 |             }
1993 |             const targetNodesList = targetTask.nodes
1994 | 
1995 |             if (!containerRef.value) return
1996 |             const rect = containerRef.value.getBoundingClientRect()
1997 | 
1998 |             const spawnX = targetClientX - rect.left
1999 |             const spawnY = targetClientY - rect.top
2000 | 
2001 |             const rawSpawnX = (spawnX - viewport.value.x) / viewport.value.zoom - (NODE_GRID_W * GRID_SIZE) / 2
2002 |             const rawSpawnY = (spawnY - viewport.value.y) / viewport.value.zoom - 40
2003 | 
2004 |             const chineseLabel = getNodeShortLabel(nodeType)
2005 |             const sameTypeCount = targetNodesList.filter(n => n.node_type === nodeType).length + 1
2006 |             const friendlyName = `${chineseLabel}_${sameTypeCount}`
2007 | 
2008 |             const newNode = {
2009 |                 node_id: newNodeId,
2010 |                 node_name: friendlyName,
2011 |                 node_type: nodeType,
2012 |                 params: {},
2013 |                 delay_before: 200,
2014 |                 loop_count: 1,
2015 |                 position: {
2016 |                     x: Math.round(rawSpawnX / GRID_SIZE) * GRID_SIZE,
2017 |                     y: Math.round(rawSpawnY / GRID_SIZE) * GRID_SIZE
2018 |                 }
2019 |             }
2020 | 
2021 |             if (sourceNodeObj) {
2022 |                 if (!sourceNodeObj.params) sourceNodeObj.params = {}
2023 | 
2024 |                 const targetTaskId = targetTask ? targetTask.task_id : ''
2025 |                 const connectionData = {
2026 |                     target_task: targetTaskId,
2027 |                     target_node: newNodeId
2028 |                 }
2029 | 
2030 |                 if (portType.startsWith('branch_')) {
2031 |                     const cIdx = parseInt(portType.split('_')[1]) || 0
2032 |                     if (sourceNodeObj.params.candidates?.[cIdx]) {
2033 |                         sourceNodeObj.params.candidates[cIdx].on_success = connectionData
2034 |                     }
2035 |                 } else if (portType === 'fail') {
2036 |                     sourceNodeObj.params.on_failure = connectionData
2037 |                 } else {
2038 |                     sourceNodeObj.params.on_success = connectionData
2039 |                 }
2040 |             }
2041 | 
2042 |             targetNodesList.push(newNode)
2043 |             store.blueprint.tasks = tasks
2044 | 
2045 |             await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)
2046 | 
2047 |             localSelectedNodeIds.value = [newNodeId]
2048 |             store.selectedNodeIds = [newNodeId]
2049 | 
2050 |             ElMessage.success(`成功创建节点: [${newNode.node_name}]`)
2051 |         } catch (err) {
2052 |             console.error('创建节点出错详情:', err)
2053 |             ElMessage.error('创建节点失败，请检查控制台日志')
2054 |         }
2055 |     }
2056 | 
2057 |     onMounted(async () => {
2058 |         window.addEventListener('mousemove', onGlobalMouseMove)
2059 |         window.addEventListener('mouseup', onGlobalMouseUp)
2060 |         window.addEventListener('keydown', globalKeydownHandler)
2061 |         window.addEventListener('keyup', globalKeyupHandler)
2062 |         if (store.currentProjectPath) {
2063 |             await store.loadProjectData()
2064 |         }
2065 |         fitViewToNodes()
2066 |         nextTick(drawMinimap)
2067 |     })
2068 | 
2069 |     onUnmounted(() => {
2070 |         window.removeEventListener('mousemove', onGlobalMouseMove)
2071 |         window.removeEventListener('mouseup', onGlobalMouseUp)
2072 |         window.removeEventListener('keydown', globalKeydownHandler)
2073 |         window.removeEventListener('keyup', globalKeyupHandler)
2074 |     })
2075 | </script>
2076 | 
2077 | <style scoped>
2078 |     .custom-canvas-container {
2079 |         width: 100%;
2080 |         height: 100%;
2081 |         background: #2b2d3d;
2082 |         position: relative;
2083 |         overflow: hidden;
2084 |         user-select: none;
2085 |     }
2086 | 
2087 |     .canvas-viewport {
2088 |         position: absolute;
2089 |         top: 0;
2090 |         left: 0;
2091 |         width: 100%;
2092 |         height: 100%;
2093 |         will-change: transform;
2094 |     }
2095 | 
2096 |     .canvas-edges-layer {
2097 |         position: absolute;
2098 |         top: 0;
2099 |         left: 0;
2100 |         width: 100%;
2101 |         height: 100%;
2102 |         pointer-events: none;
2103 |         z-index: 1;
2104 |         overflow: visible;
2105 |     }
2106 | 
2107 |     .minimap-container {
2108 |         position: absolute;
2109 |         right: 16px;
2110 |         bottom: 16px;
2111 |         width: 150px;
2112 |         height: 110px;
2113 |         background: rgba(20, 22, 34, 0.65);
2114 |         backdrop-filter: blur(8px);
2115 |         -webkit-backdrop-filter: blur(8px);
2116 |         border: 1px solid rgba(255, 255, 255, 0.08);
2117 |         border-radius: 8px;
2118 |         box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
2119 |         z-index: 998;
2120 |         overflow: hidden;
2121 |     }
2122 | 
2123 |     .canvas-group-box {
2124 |         position: absolute;
2125 |         box-sizing: border-box;
2126 |         border: 2px dashed #4ed19c;
2127 |         border-radius: 12px;
2128 |         background: rgba(78, 209, 156, 0.02);
2129 |         pointer-events: none;
2130 |         transition: border-width 0.2s ease, border-color 0.2s ease;
2131 |     }
2132 | 
2133 |         .canvas-group-box.is-focused {
2134 |             border: 3.5px solid #4ed19c;
2135 |         }
2136 | 
2137 |     .group-title-badge {
2138 |         position: absolute;
2139 |         top: -26px;
2140 |         left: 16px;
2141 |         right: 16px;
2142 |         background: var(--el-bg-color-page);
2143 |         padding: 4px 10px;
2144 |         color: #4ed19c;
2145 |         border: 1px dashed #4ed19c;
2146 |         border-radius: 6px;
2147 |         pointer-events: auto;
2148 |         cursor: grab;
2149 |         display: flex;
2150 |         flex-direction: column;
2151 |         gap: 2px;
2152 |         box-shadow: 0 2px 6px rgba(0,0,0,0.2);
2153 |     }
2154 | 
2155 |     .node-drag-preview-box {
2156 |         position: absolute;
2157 |         border: 2px dashed #4ed19c;
2158 |         background: rgba(78, 209, 156, 0.08);
2159 |         border-radius: 10px;
2160 |         pointer-events: none;
2161 |         z-index: 9;
2162 |         box-sizing: border-box;
2163 |     }
2164 | 
2165 |         .node-drag-preview-box.is-danger {
2166 |             border-color: #f56c6c;
2167 |             background: rgba(245, 108, 108, 0.12);
2168 |         }
2169 | 
2170 |     .preview-inner-tag {
2171 |         position: absolute;
2172 |         top: 6px;
2173 |         left: 8px;
2174 |         font-size: 10px;
2175 |         font-weight: bold;
2176 |         color: #4ed19c;
2177 |         background: rgba(43, 45, 61, 0.85);
2178 |         padding: 2px 6px;
2179 |         border-radius: 4px;
2180 |     }
2181 | 
2182 |     .canvas-node-card {
2183 |         position: absolute;
2184 |         background: var(--el-fill-color-blank);
2185 |         border: 1px solid var(--el-border-color-light);
2186 |         border-radius: 8px;
2187 |         padding: 8px 12px 6px 12px;
2188 |         box-shadow: 0 4px 12px rgba(0,0,0,0.3);
2189 |         cursor: grab;
2190 |         z-index: 10;
2191 |         display: flex;
2192 |         flex-direction: column;
2193 |         justify-content: space-between;
2194 |         transition: border-color 0.2s, box-shadow 0.2s;
2195 |         overflow: visible !important; /* ⚡ 允许锚点外溢 */
2196 |     }
2197 | 
2198 |         .canvas-node-card:active {
2199 |             cursor: grabbing;
2200 |         }
2201 | 
2202 |         .canvas-node-card:hover {
2203 |             border-color: #4ed19c;
2204 |             box-shadow: 0 0 10px rgba(78, 209, 156, 0.3);
2205 |         }
2206 | 
2207 |         .canvas-node-card.is-selected {
2208 |             border: 2px solid var(--el-color-primary);
2209 |             box-shadow: 0 0 12px rgba(78, 209, 156, 0.5);
2210 |         }
2211 | 
2212 |     .node-header {
2213 |         display: flex;
2214 |         justify-content: space-between;
2215 |         align-items: center;
2216 |         width: 100%;
2217 |         flex-shrink: 0;
2218 |     }
2219 | 
2220 |     .node-header-left {
2221 |         display: flex;
2222 |         align-items: center;
2223 |         gap: 6px;
2224 |     }
2225 | 
2226 |     .node-type-icon {
2227 |         width: 15px;
2228 |         height: 15px;
2229 |         color: rgba(255, 255, 255, 0.9);
2230 |         flex-shrink: 0;
2231 |     }
2232 | 
2233 |     .node-title {
2234 |         font-size: 11px;
2235 |         font-weight: 600;
2236 |         color: var(--el-text-color-primary);
2237 |     }
2238 | 
2239 |     .node-body {
2240 |         flex: 1;
2241 |         display: flex;
2242 |         flex-direction: column;
2243 |         justify-content: center;
2244 |         overflow: visible !important; /* ⚡ 核心修正：取消隐藏，拒绝裁切行级绿点 */
2245 |         margin: 4px 0;
2246 |     }
2247 | 
2248 |     /* ⚡ Branch 行级条件列表与锚点样式 */
2249 |     .branch-candidates-list {
2250 |         display: flex;
2251 |         flex-direction: column;
2252 |         gap: 4px;
2253 |         width: 100%;
2254 |         padding: 2px 0;
2255 |         overflow: visible !important;
2256 |     }
2257 | 
2258 |     .branch-candidate-item {
2259 |         position: relative;
2260 |         display: flex;
2261 |         align-items: center;
2262 |         justify-content: space-between;
2263 |         background: rgba(255, 255, 255, 0.04);
2264 |         border: 1px solid var(--el-border-color-light);
2265 |         border-radius: 4px;
2266 |         padding: 3px 6px;
2267 |         font-size: 10px;
2268 |         height: 24px;
2269 |         overflow: visible !important; /* ⚡ 允许内部锚点半嵌在卡片右侧 */
2270 |         z-index: 2;
2271 |     }
2272 | 
2273 |     .branch-cand-text {
2274 |         white-space: nowrap;
2275 |         overflow: hidden;
2276 |         text-overflow: ellipsis;
2277 |         color: var(--el-text-color-regular);
2278 |         max-width: 180px;
2279 |     }
2280 | 
2281 |     .branch-handle {
2282 |         right: -18px; /* ⚡ 核心修正：考虑到卡片内边距，使锚点精准嵌入右侧边框 */
2283 |         top: 50%;
2284 |         transform: translateY(-50%);
2285 |         background: #4ed19c;
2286 |         z-index: 10;
2287 |     }
2288 | 
2289 |     .empty-cand-placeholder {
2290 |         font-size: 10px;
2291 |         color: var(--el-text-color-placeholder);
2292 |         text-align: center;
2293 |         padding: 8px 0;
2294 |     }
2295 | 
2296 |     .node-image-embedded {
2297 |         position: relative;
2298 |         width: 100%;
2299 |         height: 100%;
2300 |         background: rgba(18, 19, 28, 0.6);
2301 |         border-radius: 6px;
2302 |         display: flex;
2303 |         align-items: center;
2304 |         justify-content: center;
2305 |         overflow: hidden;
2306 |     }
2307 | 
2308 |     .embedded-template-img {
2309 |         position: relative;
2310 |         width: 100%;
2311 |         height: 100%;
2312 |         object-fit: cover;
2313 |         border-radius: 5px;
2314 |         display: block;
2315 |         z-index: 2;
2316 |         pointer-events: none;
2317 |     }
2318 | 
2319 |         .embedded-template-img.is-contain {
2320 |             object-fit: contain !important;
2321 |         }
2322 | 
2323 |     .embedded-placeholder {
2324 |         display: flex;
2325 |         flex-direction: column;
2326 |         align-items: center;
2327 |         justify-content: center;
2328 |         font-size: 11px;
2329 |         color: var(--el-text-color-placeholder);
2330 |         z-index: 2;
2331 |     }
2332 | 
2333 |     .node-footer-bar {
2334 |         display: flex;
2335 |         justify-content: flex-start;
2336 |         align-items: center;
2337 |         gap: 6px;
2338 |         border-top: 1px solid rgba(255, 255, 255, 0.05);
2339 |         padding-top: 4px;
2340 |         margin-top: auto;
2341 |         flex-shrink: 0;
2342 |     }
2343 | 
2344 |     .footer-tag {
2345 |         font-size: 9px;
2346 |         color: var(--el-text-color-secondary);
2347 |         background: rgba(255, 255, 255, 0.04);
2348 |         padding: 1px 5px;
2349 |         border-radius: 4px;
2350 |     }
2351 | 
2352 |     .node-handle {
2353 |         position: absolute;
2354 |         width: 12px;
2355 |         height: 12px;
2356 |         border-radius: 50%;
2357 |         cursor: crosshair;
2358 |         z-index: 5;
2359 |         border: 2px solid #181926;
2360 |         transition: transform 0.15s, box-shadow 0.15s;
2361 |     }
2362 | 
2363 |         .node-handle::after {
2364 |             content: '';
2365 |             position: absolute;
2366 |             top: -10px;
2367 |             left: -10px;
2368 |             right: -10px;
2369 |             bottom: -10px;
2370 |             background: transparent;
2371 |             border-radius: 50%;
2372 |         }
2373 | 
2374 |         .node-handle:hover {
2375 |             border-color: #ffffff;
2376 |             box-shadow: 0 0 8px rgba(78, 209, 156, 0.6);
2377 |         }
2378 | 
2379 |     .top-handle {
2380 |         top: -6px;
2381 |         left: 50%;
2382 |         cursor: auto;
2383 |         transform: translateX(-50%);
2384 |         background: #181926;
2385 |         border: 2px solid #f2f2f3;
2386 |     }
2387 | 
2388 |     .succ-handle {
2389 |         bottom: -6px;
2390 |         left: 50%;
2391 |         transform: translateX(-50%);
2392 |         background: #4ed19c;
2393 |     }
2394 | 
2395 |     .fail-handle {
2396 |         right: -6px;
2397 |         top: 50%;
2398 |         transform: translateY(-50%);
2399 |         background: #f56c6c;
2400 |     }
2401 | 
2402 |     /* ⚡ 针对 Branch 节点，将 Else 兜底红点下移至右下方，避免与行级绿点覆盖 */
2403 |     .canvas-node-card:has(.branch-candidates-list) .fail-handle {
2404 |         top: auto !important;
2405 |         bottom: 12px !important;
2406 |         transform: none !important;
2407 |     }
2408 | 
2409 |     .selection-box {
2410 |         position: absolute;
2411 |         background: rgba(78, 209, 156, 0.1);
2412 |         border: 1px solid #4ed19c;
2413 |         pointer-events: none;
2414 |         z-index: 999;
2415 |     }
2416 | 
2417 |     .spawn-menu, .custom-context-menu {
2418 |         position: fixed;
2419 |         width: 180px;
2420 |         background: var(--el-bg-color-overlay, #26283d);
2421 |         border: 1px solid var(--el-border-color-light, #313352);
2422 |         border-radius: 8px;
2423 |         box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
2424 |         padding: 6px 0;
2425 |     }
2426 | 
2427 |     .menu-item {
2428 |         padding: 8px 14px;
2429 |         font-size: 12px;
2430 |         color: var(--el-text-color-regular);
2431 |         cursor: pointer;
2432 |         display: flex;
2433 |         align-items: center;
2434 |         gap: 8px;
2435 |     }
2436 | 
2437 |         .menu-item:hover {
2438 |             background: var(--el-fill-color-light);
2439 |             color: var(--el-text-color-primary);
2440 |         }
2441 | 
2442 |         .menu-item.danger:hover {
2443 |             background: rgba(245, 108, 108, 0.15);
2444 |             color: #f56c6c;
2445 |         }
2446 | 
2447 |     .menu-item-icon {
2448 |         width: 14px;
2449 |         height: 14px;
2450 |         flex-shrink: 0;
2451 |     }
2452 | 
2453 |     .edge-path {
2454 |         fill: none;
2455 |         stroke: #4ed19c;
2456 |         stroke-width: 2.5;
2457 |         pointer-events: stroke;
2458 |         cursor: pointer;
2459 |         transition: stroke 0.2s;
2460 |     }
2461 | 
2462 |     .edge-flow-path {
2463 |         fill: none;
2464 |         stroke: #ffffff;
2465 |         stroke-width: 2.5;
2466 |         stroke-dasharray: 8 16;
2467 |         animation: flowAnimation 0.8s linear infinite;
2468 |         opacity: 0.85;
2469 |     }
2470 | 
2471 |         .edge-flow-path.is-danger {
2472 |             stroke: #ffadad;
2473 |         }
2474 | 
2475 |     @keyframes flowAnimation {
2476 |         from {
2477 |             stroke-dashoffset: 24;
2478 |         }
2479 | 
2480 |         to {
2481 |             stroke-dashoffset: 0;
2482 |         }
2483 |     }
2484 | 
2485 |     .edge-path:hover, .edge-path.is-selected {
2486 |         stroke: #ffffff;
2487 |         stroke-width: 4;
2488 |         filter: drop-shadow(0 0 6px #4ed19c);
2489 |     }
2490 | 
2491 |     .edge-path.is-danger {
2492 |         stroke: #f56c6c;
2493 |     }
2494 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\canvas\CanvasLogPanel.vue

- Extension: .vue
- Language: unknown
- Size: 3042 bytes
- Created: 2026-08-08 21:36:57
- Modified: 2026-08-10 11:34:11

### Code

```unknown
  1 | ﻿<!-- frontend/src/components/canvas/CanvasLogPanel.vue -->
  2 | <template>
  3 |     <div class="canvas-log-panel-embedded">
  4 |         <div ref="logBodyRef" class="log-panel-body">
  5 |             <div v-if="!logs.length" class="log-placeholder-text">暂无最新运行日志输出...</div>
  6 |             <div v-for="(item, idx) in logs"
  7 |                  :key="idx"
  8 |                  class="log-line"
  9 |                  :class="getLogLevelClass(item)">
 10 |                 <span class="log-time">[{{ getItemTime(item) }}]</span>
 11 |                 <span class="log-text">{{ getItemText(item) }}</span>
 12 |             </div>
 13 |         </div>
 14 |     </div>
 15 | </template>
 16 | 
 17 | <script setup>
 18 |     import { ref, computed, watch, nextTick } from 'vue'
 19 |     import { useMainStore } from '@/stores'
 20 | 
 21 |     const store = useMainStore()
 22 |     const logBodyRef = ref(null)
 23 | 
 24 |     const logs = computed(() => store.executionLogs || [])
 25 | 
 26 |     const getItemTime = (item) => {
 27 |         if (typeof item === 'object' && item !== null) return item.time || 'INFO'
 28 |         return 'INFO'
 29 |     }
 30 | 
 31 |     const getItemText = (item) => {
 32 |         if (typeof item === 'object' && item !== null) return item.message || JSON.stringify(item)
 33 |         return String(item)
 34 |     }
 35 | 
 36 |     const getLogLevelClass = (item) => {
 37 |         const msg = getItemText(item)
 38 |         if (msg.includes('💥') || msg.includes('❌') || msg.includes('ERROR')) return 'log-error'
 39 |         if (msg.includes('⚠️') || msg.includes('WARNING')) return 'log-warn'
 40 |         if (msg.includes('🎯') || msg.includes('✅')) return 'log-success'
 41 |         return 'log-info'
 42 |     }
 43 | 
 44 |     watch(() => logs.value.length, () => {
 45 |         nextTick(() => {
 46 |             if (logBodyRef.value) {
 47 |                 logBodyRef.value.scrollTop = logBodyRef.value.scrollHeight
 48 |             }
 49 |         })
 50 |     })
 51 | </script>
 52 | 
 53 | <style scoped>
 54 |     .canvas-log-panel-embedded {
 55 |         width: 100%;
 56 |         height: 100%;
 57 |         background: var(--el-bg-color);
 58 |         display: flex;
 59 |         flex-direction: column;
 60 |         overflow: hidden;
 61 |         user-select: text;
 62 |     }
 63 | 
 64 |     .log-panel-body {
 65 |         flex: 1;
 66 |         padding: 8px 12px;
 67 |         font-size: 11px;
 68 |         color: var(--el-text-color-regular);
 69 |         overflow-y: auto;
 70 |         font-family: 'Consolas', 'Courier New', monospace;
 71 |     }
 72 | 
 73 |     .log-placeholder-text {
 74 |         color: var(--el-text-color-placeholder);
 75 |         text-align: center;
 76 |         padding: 10px 0;
 77 |     }
 78 | 
 79 |     .log-line {
 80 |         font-size: 11px;
 81 |         line-height: 1.5;
 82 |         white-space: pre-wrap;
 83 |         word-break: break-all;
 84 |         display: flex;
 85 |         gap: 6px;
 86 |     }
 87 | 
 88 |     .log-time {
 89 |         color: var(--el-text-color-secondary);
 90 |         flex-shrink: 0;
 91 |     }
 92 | 
 93 |     .log-info {
 94 |         color: var(--el-text-color-regular);
 95 |     }
 96 | 
 97 |     .log-success {
 98 |         color: var(--el-color-primary);
 99 |     }
100 | 
101 |     .log-warn {
102 |         color: #e6a23c;
103 |     }
104 | 
105 |     .log-error {
106 |         color: #f56c6c;
107 |         font-weight: bold;
108 |     }
109 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\conditions\ConditionDialog.vue

- Extension: .vue
- Language: unknown
- Size: 10119 bytes
- Created: 2026-08-11 10:27:12
- Modified: 2026-08-12 11:47:50

### Code

```unknown
  1 | <!-- frontend/src/components/conditions/ConditionDialog.vue -->
  2 | <template>
  3 |     <el-dialog v-model="dialogVisible"
  4 |                :title="isBranch ? '⚙️ 设置分流条件分支' : '➕ 设置判定条件'"
  5 |                width="560px"
  6 |                append-to-body
  7 |                destroy-on-close
  8 |                :close-on-click-modal="false"
  9 |                custom-class="condition-dialog-custom">
 10 |         <div class="condition-form-body">
 11 |             <!-- 1. 条件类别切换 (5大判定场景) -->
 12 |             <div class="type-selector-item">
 13 |                 <span class="selector-label">条件判定类型</span>
 14 |                 <el-select v-model="activeConditionType"
 15 |                            placeholder="请选择条件类型"
 16 |                            style="width: 100%"
 17 |                            @change="handleTypeChange">
 18 |                     <el-option label="🖼️ 屏幕/区域存在指定图片" value="image_exists" />
 19 |                     <el-option label="🔤 屏幕/区域包含指定文本 (OCR)" value="text_contains" />
 20 |                     <el-option label="🔢 变量数值/逻辑比较" value="variable_check" />
 21 |                     <el-option label="🪟 指定窗口状态 (存在/激活/关闭)" value="window_state" />
 22 |                     <el-option label="📂 本地文件/文件夹是否存在" value="file_exists" />
 23 |                 </el-select>
 24 |             </div>
 25 | 
 26 |             <!-- 2. Schema 驱动的通用原子控件分发表单 -->
 27 |             <div class="schema-rendered-container">
 28 |                 <template v-for="(config, paramName) in currentParamsSchema" :key="paramName">
 29 |                     <!-- 灰度阈值滑块定制优化 -->
 30 |                     <div v-if="paramName === 'gray_threshold' && conditionPayload.gray_scale"
 31 |                          class="param-item-wrapper slider-box">
 32 |                         <div class="slider-header">
 33 |                             <span>二值化灰度阈值: <strong>{{ conditionPayload.gray_threshold ?? 127 }}</strong></span>
 34 |                             <span class="slider-tip">(向左增强浅色，向右过滤背景)</span>
 35 |                         </div>
 36 |                         <el-slider v-model="conditionPayload.gray_threshold"
 37 |                                    :min="0"
 38 |                                    :max="255"
 39 |                                    :step="1"
 40 |                                    @input="val => handleParamChange('gray_threshold', val)" />
 41 |                     </div>
 42 | 
 43 |                     <!-- 统一原子控件渲染 -->
 44 |                     <div v-else-if="paramName !== 'gray_threshold'" class="param-item-wrapper">
 45 |                         <ParamRenderer :config="config"
 46 |                                        :value="conditionPayload[paramName]"
 47 |                                        :label="config.label || paramName"
 48 |                                        :context="conditionPayload"
 49 |                                        @update="val => handleParamChange(paramName, val)"
 50 |                                        @open-browser="mode => $emit('open-browser', mode)"
 51 |                                        @open-screenshot="mode => $emit('open-screenshot', mode)" />
 52 |                     </div>
 53 |                 </template>
 54 |             </div>
 55 |         </div>
 56 | 
 57 |         <template #footer>
 58 |             <div class="dialog-footer">
 59 |                 <el-button @click="dialogVisible = false">取消</el-button>
 60 |                 <el-button type="primary" @click="handleSave">确认保存</el-button>
 61 |             </div>
 62 |         </template>
 63 |     </el-dialog>
 64 | </template>
 65 | 
 66 | <script setup>
 67 |     import { ref, computed, watch } from 'vue'
 68 |     import ParamRenderer from '@/components/ParamRenderer.vue'
 69 |     import { CONDITION_SCHEMAS } from './conditionSchemas.js'
 70 |     import { useMainStore } from '@/stores'
 71 |     import { visionApi } from '@/api/visionApi'
 72 |     import { ElMessage } from 'element-plus'
 73 | 
 74 |     const props = defineProps({
 75 |         visible: { type: Boolean, default: false },
 76 |         showJumpConfig: { type: Boolean, default: false },
 77 |         initialData: { type: Object, default: null }
 78 |     })
 79 | 
 80 |     const emit = defineEmits(['update:visible', 'save', 'open-browser', 'open-screenshot'])
 81 |     const store = useMainStore()
 82 | 
 83 |     const dialogVisible = computed({
 84 |         get: () => props.visible,
 85 |         set: (val) => emit('update:visible', val)
 86 |     })
 87 | 
 88 |     const isBranch = computed(() => props.showJumpConfig)
 89 |     const activeConditionType = ref('image_exists')
 90 |     const conditionPayload = ref({})
 91 | 
 92 |     const currentParamsSchema = computed(() => {
 93 |         return CONDITION_SCHEMAS[activeConditionType.value]?.params || {}
 94 |     })
 95 | 
 96 |     const initDefaultPayload = (type) => {
 97 |         const schema = CONDITION_SCHEMAS[type]?.params || {}
 98 |         const payload = { condition_type: type }
 99 |         Object.keys(schema).forEach(key => {
100 |             payload[key] = schema[key].default
101 |         })
102 |         return payload
103 |     }
104 | 
105 |     const handleTypeChange = (newType) => {
106 |         conditionPayload.value = initDefaultPayload(newType)
107 |     }
108 | 
109 |     // ⚡ 1. 精准提取并清洗模板名称，自动同步更新到 Schema 对应字段 region_value
110 |     const autoFillRecordedRegion = async (imageSource) => {
111 |         const projectPath = store.currentProjectPath || ''
112 |         if (!imageSource || !projectPath) return
113 | 
114 |         try {
115 |             console.log('🔍 [录制坐标获取] 发起请求:', { projectPath, imageSource })
116 |             const res = await visionApi.getRegions(projectPath)
117 |             const regions = res?.data || res || {}
118 |             console.log('📦 [后端返回 Regions 字典]:', regions)
119 | 
120 |             // 名字清洗（去除路径和 .png 扩展名，如 'sub/21.png' -> '21'）
121 |             const cleanKey = imageSource.replace(/\\/g, '/').split('/').pop().replace(/\.(png|jpg|jpeg)$/i, '')
122 |             const recordedBox = regions[cleanKey] || regions[imageSource] || regions[`${cleanKey}.png`]
123 | 
124 |             if (Array.isArray(recordedBox) && recordedBox.length >= 4) {
125 |                 console.log('🎯 [成功匹配坐标]:', recordedBox)
126 | 
127 |                 // ⚡ 核心修补：同时对 Schema 中定义的 region_value 赋值，确保 ParamRenderer 与 ControlCoordPicker 正确刷新！
128 |                 const targetBox = [...recordedBox]
129 |                 conditionPayload.value.region_value = targetBox
130 |                 conditionPayload.value.crop_rect = targetBox
131 |                 conditionPayload.value.region = targetBox
132 | 
133 |                 ElMessage.success(`已自动带入图片 [${cleanKey}] 录制坐标: [${targetBox.join(', ')}]`)
134 |             } else {
135 |                 console.warn('⚠️ [未找到匹配坐标 Key], 当前可用的 Keys:', Object.keys(regions))
136 |                 conditionPayload.value.region_value = [0, 0, 0, 0]
137 |                 conditionPayload.value.crop_rect = [0, 0, 0, 0]
138 |                 conditionPayload.value.region = [0, 0, 0, 0]
139 |                 ElMessage.warning(`未找到图片 [${cleanKey}] 的录制坐标，已重置为 [0,0,0,0]`)
140 |             }
141 | 
142 |             // ⚡ 触发顶级响应式更新
143 |             conditionPayload.value = { ...conditionPayload.value }
144 |         } catch (err) {
145 |             console.error('获取录制坐标失败:', err)
146 |         }
147 |     }
148 | 
149 |     // ⚡ 2. 监听控件更新事件 (同时兼顾 region_type 和 match_mode)
150 |     const handleParamChange = async (paramName, val) => {
151 |         conditionPayload.value[paramName] = val
152 | 
153 |         const isRecordedMode = (paramName === 'region_type' || paramName === 'match_mode') && val === 'recorded'
154 |         const isImageChangeInRecordedMode = paramName === 'image_source' && (conditionPayload.value.region_type === 'recorded' || conditionPayload.value.match_mode === 'recorded')
155 | 
156 |         if (isRecordedMode || isImageChangeInRecordedMode) {
157 |             await autoFillRecordedRegion(conditionPayload.value.image_source)
158 |         }
159 | 
160 |         conditionPayload.value = { ...conditionPayload.value }
161 |     }
162 | 
163 |     watch(() => props.visible, (val) => {
164 |         if (val) {
165 |             if (props.initialData) {
166 |                 const initCond = props.initialData.condition || props.initialData
167 |                 activeConditionType.value = initCond.condition_type || 'image_exists'
168 |                 conditionPayload.value = JSON.parse(JSON.stringify(initCond))
169 |             } else {
170 |                 activeConditionType.value = 'image_exists'
171 |                 conditionPayload.value = initDefaultPayload('image_exists')
172 |             }
173 |         }
174 |     })
175 | 
176 |     const handleSave = () => {
177 |         emit('save', {
178 |             condition: conditionPayload.value,
179 |             on_success: props.initialData?.on_success || {}
180 |         })
181 |         dialogVisible.value = false
182 |     }
183 | </script>
184 | 
185 | <style scoped>
186 |     .condition-form-body {
187 |         display: flex;
188 |         flex-direction: column;
189 |         gap: 14px;
190 |         max-height: 65vh;
191 |         overflow-y: auto;
192 |         padding-right: 4px;
193 |     }
194 | 
195 |     .type-selector-item {
196 |         display: flex;
197 |         flex-direction: column;
198 |         gap: 6px;
199 |     }
200 | 
201 |     .selector-label {
202 |         font-size: 13px;
203 |         font-weight: 600;
204 |         color: var(--el-text-color-primary);
205 |     }
206 | 
207 |     .schema-rendered-container {
208 |         display: flex;
209 |         flex-direction: column;
210 |         gap: 12px;
211 |     }
212 | 
213 |     .param-item-wrapper {
214 |         width: 100%;
215 |     }
216 | 
217 |     .slider-box {
218 |         background: var(--el-fill-color-blank);
219 |         padding: 10px 12px;
220 |         border-radius: 8px;
221 |         border: 1px solid var(--el-border-color-light);
222 |     }
223 | 
224 |     .slider-header {
225 |         display: flex;
226 |         justify-content: space-between;
227 |         font-size: 12px;
228 |         color: var(--el-text-color-primary);
229 |         margin-bottom: 4px;
230 |     }
231 | 
232 |     .slider-tip {
233 |         color: var(--el-text-color-secondary);
234 |         font-size: 11px;
235 |     }
236 | 
237 |     .dialog-footer {
238 |         display: flex;
239 |         justify-content: flex-end;
240 |         gap: 10px;
241 |     }
242 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\conditions\conditionSchemas.js

- Extension: .js
- Language: javascript
- Size: 7659 bytes
- Created: 2026-08-11 17:18:02
- Modified: 2026-08-11 18:08:51

### Code

```javascript
  1 | // frontend/src/components/conditions/conditionSchemas.js
  2 | 
  3 | export const CONDITION_SCHEMAS = {
  4 |     // 1. 屏幕/区域存在指定图片 (图像判定)
  5 |     image_exists: {
  6 |         label: "屏幕/区域存在指定图片",
  7 |         params: {
  8 |             exist_mode: {
  9 |                 type: "select",
 10 |                 label: "判定要求",
 11 |                 default: "exists",
 12 |                 options: [
 13 |                     { label: "屏幕/区域存在该图片", value: "exists" },
 14 |                     { label: "屏幕/区域不存在该图片", value: "not_exists" }
 15 |                 ]
 16 |             },
 17 |             image_source: {
 18 |                 type: "file",
 19 |                 default: "",
 20 |                 label: "模板图片"
 21 |             },
 22 |             gray_scale: {
 23 |                 type: "bool",
 24 |                 default: true,
 25 |                 label: "去除背景干扰 (灰度处理)"
 26 |             },
 27 |             gray_threshold: {
 28 |                 type: "int",
 29 |                 default: 127,
 30 |                 label: "二值化灰度阈值 (0-255，调节至轮廓最清晰)",
 31 |                 min: 0,
 32 |                 max: 255,
 33 |                 step: 1,
 34 |                 visible_if: {
 35 |                     field: "gray_scale",
 36 |                     operator: "eq",
 37 |                     value: true
 38 |                 }
 39 |             },
 40 |             threshold: {
 41 |                 type: "int",
 42 |                 default: 85,
 43 |                 label: "匹配相似度",
 44 |                 suffix: "%",
 45 |                 min: 1,
 46 |                 max: 100
 47 |             },
 48 |             region_type: {
 49 |                 type: "select",
 50 |                 options: [
 51 |                     { value: "fullwindow", label: "整个工作面板" },
 52 |                     { value: "recorded", label: "录制时的坐标区域" },
 53 |                     { value: "custom", label: "自定义区域" }
 54 |                 ],
 55 |                 default: "recorded",
 56 |                 label: "匹配区域"
 57 |             },
 58 |             region_value: {
 59 |                 type: "list_int4_picker",
 60 |                 default: [0, 0, 0, 0],
 61 |                 label: "匹配区域坐标",
 62 |                 visible_if: {
 63 |                     field: "region_type",
 64 |                     operator: "in",
 65 |                     value: ["recorded", "custom"]
 66 |                 }
 67 |             }
 68 |         }
 69 |     },
 70 | 
 71 |     // 2. 屏幕/区域包含指定文本 (OCR 判定)
 72 |     text_contains: {
 73 |         label: "屏幕/区域包含指定文本 (OCR)",
 74 |         params: {
 75 |             exist_mode: {
 76 |                 type: "select",
 77 |                 label: "判定要求",
 78 |                 default: "contains",
 79 |                 options: [
 80 |                     { label: "区域文本包含目标内容", value: "contains" },
 81 |                     { label: "区域文本不包含目标内容", value: "not_contains" },
 82 |                     { label: "区域文本完全等于目标内容", value: "equals" }
 83 |                 ]
 84 |             },
 85 |             target_text: {
 86 |                 type: "str",  // ⚡ 修正：改为常规字符串输入框，方便打字
 87 |                 default: "",
 88 |                 label: "期望对比的文本内容",
 89 |                 placeholder: "请输入固定文本或变量如 {var_name}"
 90 |             },
 91 |             image_source: {
 92 |                 type: "file",
 93 |                 default: "",
 94 |                 label: "OCR 文本视角模板"
 95 |             },
 96 |             gray_scale: {
 97 |                 type: "bool",
 98 |                 default: true,
 99 |                 label: "去除背景干扰 (灰度处理)"
100 |             },
101 |             gray_threshold: {
102 |                 type: "int",
103 |                 default: 127,
104 |                 label: "二值化灰度阈值 (0-255，调节至文字最清晰)",
105 |                 min: 0,
106 |                 max: 255,
107 |                 step: 1,
108 |                 visible_if: {
109 |                     field: "gray_scale",
110 |                     operator: "eq",
111 |                     value: true
112 |                 }
113 |             },
114 |             region_type: {
115 |                 type: "select",
116 |                 options: [
117 |                     { value: "fullwindow", label: "整个工作面板" },
118 |                     { value: "recorded", label: "录制时的坐标区域" },
119 |                     { value: "custom", label: "自定义区域" }
120 |                 ],
121 |                 default: "recorded",
122 |                 label: "识别区域"
123 |             },
124 |             region_value: {
125 |                 type: "list_int4_picker",
126 |                 default: [0, 0, 0, 0],
127 |                 label: "识别区域坐标",
128 |                 visible_if: {
129 |                     field: "region_type",
130 |                     operator: "in",
131 |                     value: ["recorded", "custom"]
132 |                 }
133 |             }
134 |         }
135 |     },
136 | 
137 |     // 3. 变量数值/逻辑比较
138 |     variable_check: {
139 |         label: "变量数值/逻辑比较",
140 |         params: {
141 |             variable_name: {
142 |                 type: "variable",  // ⚡ 保留强变量选择：比较变量必须选择已有变量名
143 |                 default: "",
144 |                 label: "比较变量",
145 |                 placeholder: "请选择变量名"
146 |             },
147 |             operator: {
148 |                 type: "select",
149 |                 default: "eq",
150 |                 label: "比较运算符",
151 |                 options: [
152 |                     { label: "等于 (==)", value: "eq" },
153 |                     { label: "不等于 (!=)", value: "ne" },
154 |                     { label: "大于 (>)", value: "gt" },
155 |                     { label: "大于等于 (>=)", value: "gte" },
156 |                     { label: "小于 (<)", value: "lt" },
157 |                     { label: "小于等于 (<=)", value: "lte" },
158 |                     { label: "包含 (Contains)", value: "contains" }
159 |                 ]
160 |             },
161 |             compare_value: {
162 |                 type: "str",  // ⚡ 修正：改为常规输入框，既可填数字字符串也可引用变量
163 |                 default: "",
164 |                 label: "目标对比值",
165 |                 placeholder: "请输入数值、常数或 {var_name}"
166 |             }
167 |         }
168 |     },
169 | 
170 |     // 4. 指定窗口状态 (存在/激活/关闭)
171 |     window_state: {
172 |         label: "指定窗口状态",
173 |         params: {
174 |             window_title: {
175 |                 type: "window_select",
176 |                 default: "",
177 |                 label: "目标窗口名称"
178 |             },
179 |             state_check: {
180 |                 type: "select",
181 |                 default: "exists",
182 |                 label: "期望窗口状态",
183 |                 options: [
184 |                     { label: "窗口存在", value: "exists" },
185 |                     { label: "窗口不存在", value: "not_exists" },
186 |                     { label: "窗口处于前台激活", value: "active" }
187 |                 ]
188 |             }
189 |         }
190 |     },
191 | 
192 |     // 5. 本地文件/文件夹是否存在
193 |     file_exists: {
194 |         label: "本地文件/文件夹状态",
195 |         params: {
196 |             file_path: {
197 |                 type: "str",
198 |                 default: "",
199 |                 label: "文件/目录绝对路径",
200 |                 placeholder: "如 D:/data/config.json"
201 |             },
202 |             check_type: {
203 |                 type: "select",
204 |                 default: "exists",
205 |                 label: "检查模式",
206 |                 options: [
207 |                     { label: "文件或目录存在", value: "exists" },
208 |                     { label: "文件或目录不存在", value: "not_exists" }
209 |                 ]
210 |             }
211 |         }
212 |     }
213 | }
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\conditions\index.js

- Extension: .js
- Language: javascript
- Size: 218 bytes
- Created: 2026-08-11 10:27:19
- Modified: 2026-08-11 17:32:00

### Code

```javascript
1 | // frontend/src/components/conditions/index.js
2 | import ConditionDialog from './ConditionDialog.vue'
3 | import { CONDITION_SCHEMAS } from './conditionSchemas.js'
4 | 
5 | export {
6 |     ConditionDialog,
7 |     CONDITION_SCHEMAS
8 | }
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlConditionList.vue

- Extension: .vue
- Language: unknown
- Size: 5315 bytes
- Created: 2026-08-08 21:13:11
- Modified: 2026-08-12 11:31:59

### Code

```unknown
  1 | <!-- frontend/src/components/controls/ControlConditionList.vue -->
  2 | <template>
  3 |     <div class="condition-list-wrapper">
  4 |         <!-- 1. 普通条件检测节点 (用于 LogicCheck 节点) -->
  5 |         <template v-if="config.type === 'condition_list_editor' || config.type === 'condition_list'">
  6 |             <div v-for="(cond, idx) in (modelValue || [])" :key="idx" class="cond-card">
  7 |                 <div class="card-info">
  8 |                     <span class="cond-desc">{{ formatCondDesc(cond) }}</span>
  9 |                 </div>
 10 |                 <div class="card-btns">
 11 |                     <el-button link size="small" type="primary" @click="$emit('open-cond-dialog', { idx, data: cond, isBranch: false })">编辑</el-button>
 12 |                     <el-button link size="small" type="danger" @click="removeCond(idx)">删除</el-button>
 13 |                 </div>
 14 |             </div>
 15 |             <el-button type="primary" size="small" class="add-btn" @click="$emit('open-cond-dialog', { idx: -1, data: null, isBranch: false })">
 16 |                 ➕ 添加判断条件
 17 |             </el-button>
 18 |         </template>
 19 | 
 20 |         <!-- 2. 分流分支候选列表 (用于 Branch 多分支节点，已彻底隐藏“成功跳转”冗余提示) -->
 21 |         <template v-else-if="config.type === 'branch_candidate_editor' || config.type === 'candidates'">
 22 |             <div v-for="(cand, idx) in (modelValue || [])" :key="idx" class="cond-card">
 23 |                 <div class="card-info">
 24 |                     <div class="cond-desc">{{ formatCondDesc(cand.condition || cand) }}</div>
 25 |                 </div>
 26 |                 <div class="card-btns">
 27 |                     <el-button link size="small" type="primary" @click="$emit('open-cond-dialog', { idx, data: cand, isBranch: true })">编辑分支</el-button>
 28 |                     <el-button link size="small" type="danger" @click="removeCond(idx)">删除</el-button>
 29 |                 </div>
 30 |             </div>
 31 |             <el-button type="success" size="small" class="add-btn" @click="$emit('open-cond-dialog', { idx: -1, data: null, isBranch: true })">
 32 |                 🔀 添加分流条件分支
 33 |             </el-button>
 34 |         </template>
 35 |     </div>
 36 | </template>
 37 | 
 38 | <script setup>
 39 |     const props = defineProps({
 40 |         config: { type: Object, required: true },
 41 |         modelValue: { type: Array, default: () => [] }
 42 |     })
 43 | 
 44 |     const emit = defineEmits(['update:modelValue', 'open-cond-dialog'])
 45 | 
 46 |     const removeCond = (idx) => {
 47 |         const updated = [...(props.modelValue || [])]
 48 |         updated.splice(idx, 1)
 49 |         emit('update:modelValue', updated)
 50 |     }
 51 | 
 52 |     // 智能格式化动态 Schema 的条件预览描述
 53 |     const formatCondDesc = (item) => {
 54 |         if (!item) return '未配置条件'
 55 |         const condType = item.condition_type || item.type || 'variable_check'
 56 |         const params = item.params || item
 57 | 
 58 |         if (condType === 'image_exists') {
 59 |             const opText = params.exist_mode === 'not_exists' ? '屏幕不存在' : '屏幕存在'
 60 |             return `🖼️ ${opText} 图片: [${params.image_source || '未选图片'}]`
 61 |         }
 62 | 
 63 |         if (condType === 'text_contains') {
 64 |             const modeMap = { contains: '包含', not_contains: '不包含', equals: '等于' }
 65 |             const modeText = modeMap[params.exist_mode] || '包含'
 66 |             return `🔤 屏幕文本 (${modeText}): [${params.target_text || '未设文本'}]`
 67 |         }
 68 | 
 69 |         if (condType === 'variable_check') {
 70 |             const varName = params.variable_name || params.var_name || '未选变量'
 71 |             const op = params.operator || 'eq'
 72 |             const val = params.compare_value ?? params.target_value ?? ''
 73 |             return `🔢 变量判定: ${varName} (${op}) ${val}`
 74 |         }
 75 | 
 76 |         if (condType === 'window_state') {
 77 |             return `🪟 窗口状态: [${params.window_title || '默认窗口'}] (${params.state_check || '存在'})`
 78 |         }
 79 | 
 80 |         if (condType === 'file_exists') {
 81 |             return `📂 文件检查: [${params.file_path || '未设路径'}]`
 82 |         }
 83 | 
 84 |         return `判定类型: ${condType}`
 85 |     }
 86 | </script>
 87 | 
 88 | <style scoped>
 89 |     .condition-list-wrapper {
 90 |         display: flex;
 91 |         flex-direction: column;
 92 |         gap: 8px;
 93 |         width: 100%;
 94 |     }
 95 | 
 96 |     .cond-card {
 97 |         display: flex;
 98 |         justify-content: space-between;
 99 |         align-items: center;
100 |         padding: 8px 10px;
101 |         background: var(--el-fill-color-blank);
102 |         border: 1px solid var(--el-border-color-light);
103 |         border-radius: var(--app-radius-sm, 6px);
104 |         font-size: 12px;
105 |         color: var(--el-text-color-regular);
106 |         gap: 8px;
107 |     }
108 | 
109 |     .card-info {
110 |         display: flex;
111 |         flex-direction: column;
112 |         gap: 2px;
113 |         flex: 1;
114 |         overflow: hidden;
115 |     }
116 | 
117 |     .cond-desc {
118 |         word-break: break-all;
119 |         font-weight: 500;
120 |         color: var(--el-text-color-primary);
121 |         white-space: nowrap;
122 |         overflow: hidden;
123 |         text-overflow: ellipsis;
124 |     }
125 | 
126 |     .card-btns {
127 |         display: flex;
128 |         align-items: center;
129 |         gap: 4px;
130 |         flex-shrink: 0;
131 |     }
132 | 
133 |     .add-btn {
134 |         width: 100%;
135 |         margin-top: 4px;
136 |     }
137 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlCoordPicker.vue

- Extension: .vue
- Language: unknown
- Size: 4196 bytes
- Created: 2026-08-08 21:12:57
- Modified: 2026-08-12 11:48:28

### Code

```unknown
  1 | <!-- frontend/src/components/controls/ControlCoordPicker.vue -->
  2 | <template>
  3 |     <div class="coord-picker-wrapper">
  4 |         <!-- 顶栏：左侧标题，右侧“取点 / 框选区域”按钮 -->
  5 |         <div class="coord-header-row">
  6 |             <span class="coord-title">{{ label }}</span>
  7 |             <button type="button"
  8 |                     class="app-btn-secondary"
  9 |                     @click="$emit('openScreenshot', is2D ? 'point' : 'region')">
 10 |                 <component :is="is2D ? MapPinned : SquareDashedMousePointer" class="app-btn-icon" />
 11 |                 <span>{{ is2D ? '取点' : '框选区域' }}</span>
 12 |             </button>
 13 |         </div>
 14 | 
 15 |         <!-- 数值输入控件行 (统一遍历渲染，精简 template) -->
 16 |         <div class="coord-row">
 17 |             <div v-for="(tag, idx) in activeTags" :key="tag" class="coord-item">
 18 |                 <span class="coord-tag">{{ tag }}</span>
 19 |                 <el-input-number v-model="coordValue[idx]" :min="0" :controls="false" size="small" @change="updateVal" />
 20 |             </div>
 21 |         </div>
 22 |     </div>
 23 | </template>
 24 | 
 25 | <script setup>
 26 |     // ControlCoordPicker.vue script 部分
 27 |     import { computed, ref, watch } from 'vue'
 28 |     import { MapPinned, SquareDashedMousePointer } from 'lucide-vue-next'
 29 | 
 30 |     const props = defineProps({
 31 |         config: { type: Object, required: true },
 32 |         modelValue: { type: Array, default: () => [] },
 33 |         value: { type: Array, default: () => [] },
 34 |         label: { type: String, default: '' }
 35 |     })
 36 | 
 37 |     const emit = defineEmits(['update:modelValue', 'update', 'openScreenshot'])
 38 | 
 39 |     const is2D = computed(() => props.config.type && props.config.type.startsWith('list_int2'))
 40 |     const activeTags = computed(() => is2D.value ? ['X', 'Y'] : ['X', 'Y', 'W', 'H'])
 41 | 
 42 |     const normalizeValue = (val) => {
 43 |         const arr = Array.isArray(val) ? val : []
 44 |         const targetLen = is2D.value ? 2 : 4
 45 |         const result = []
 46 |         for (let i = 0; i < targetLen; i++) {
 47 |             result[i] = Number(arr[i]) || 0
 48 |         }
 49 |         return result
 50 |     }
 51 | 
 52 |     const coordValue = ref(normalizeValue(props.modelValue || props.value))
 53 | 
 54 |     // ⚡ 增强 watch：兼容 modelValue 和 value 两种通信方式
 55 |     watch(() => props.modelValue || props.value, (newVal) => {
 56 |         coordValue.value = normalizeValue(newVal)
 57 |     }, { deep: true, immediate: true })
 58 | 
 59 |     const updateVal = () => {
 60 |         emit('update:modelValue', [...coordValue.value])
 61 |         emit('update', [...coordValue.value])
 62 |     }
 63 | </script>
 64 | 
 65 | <style scoped>
 66 |     .coord-picker-wrapper {
 67 |         width: 100%;
 68 |         display: flex;
 69 |         flex-direction: column;
 70 |         gap: 6px;
 71 |         margin-bottom: 8px;
 72 |     }
 73 | 
 74 |     .coord-header-row {
 75 |         display: flex;
 76 |         justify-content: space-between;
 77 |         align-items: center;
 78 |         width: 100%;
 79 |     }
 80 | 
 81 |     .coord-title {
 82 |         font-size: 13px;
 83 |         color: var(--el-text-color-primary);
 84 |         font-weight: 500;
 85 |     }
 86 | 
 87 |     .coord-row {
 88 |         display: flex;
 89 |         gap: 6px;
 90 |         width: 100%;
 91 |     }
 92 | 
 93 |     .coord-item {
 94 |         flex: 1;
 95 |         display: flex;
 96 |         align-items: center;
 97 |         background: var(--el-fill-color-blank);
 98 |         border: 1px solid var(--el-border-color-light);
 99 |         border-radius: var(--app-radius-sm, 4px);
100 |         padding: 2px 4px;
101 |     }
102 | 
103 |     .coord-tag {
104 |         font-size: 11px;
105 |         color: var(--el-text-color-secondary);
106 |         font-weight: 500;
107 |         margin-right: 2px;
108 |     }
109 | 
110 |     :deep(.el-input-number) {
111 |         width: 100% !important;
112 |         background-color: transparent !important;
113 |         border: none !important;
114 |     }
115 | 
116 |     :deep(.el-input-number__decrease),
117 |     :deep(.el-input-number__increase) {
118 |         display: none !important;
119 |     }
120 | 
121 |     :deep(.el-input-number .el-input__wrapper) {
122 |         background-color: transparent !important;
123 |         box-shadow: none !important;
124 |         padding: 0 !important;
125 |     }
126 | 
127 |     :deep(.el-input-number .el-input__inner) {
128 |         text-align: center !important;
129 |         color: var(--el-text-color-primary) !important;
130 |     }
131 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlDict.vue

- Extension: .vue
- Language: unknown
- Size: 1234 bytes
- Created: 2026-08-08 21:13:04
- Modified: 2026-08-10 17:15:37

### Code

```unknown
 1 | <!-- frontend/src/components/controls/ControlDict.vue -->
 2 | <template>
 3 |     <div class="dict-container">
 4 |         <ParamRenderer v-for="(subConfig, subKey) in config.sub"
 5 |                        :key="subKey"
 6 |                        :config="subConfig"
 7 |                        :value="localDict ? localDict[subKey] : undefined"
 8 |                        :label="subConfig.label || subKey"
 9 |                        :context="localDict"
10 |                        @update="val => handleSubUpdate(subKey, val)" />
11 |     </div>
12 | </template>
13 | 
14 | <script setup>
15 | import { computed } from 'vue'
16 | import ParamRenderer from '@/components/ParamRenderer.vue'
17 | 
18 | const props = defineProps({
19 |   config: { type: Object, required: true },
20 |   modelValue: { type: Object, default: () => ({}) }
21 | })
22 | 
23 | const emit = defineEmits(['update:modelValue'])
24 | 
25 | const localDict = computed(() => props.modelValue || {})
26 | 
27 | const handleSubUpdate = (subKey, val) => {
28 |   const updated = { ...localDict.value, [subKey]: val }
29 |   emit('update:modelValue', updated)
30 | }
31 | </script>
32 | 
33 | <style scoped>
34 |     .dict-container {
35 |         padding-left: 12px;
36 |         border-left: 2px solid var(--el-border-color-light);
37 |         margin-top: 4px;
38 |         width: 100%;
39 |     }
40 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlFileHover.vue

- Extension: .vue
- Language: unknown
- Size: 8028 bytes
- Created: 2026-08-08 21:12:50
- Modified: 2026-08-11 12:11:23

### Code

```unknown
  1 | <!-- frontend/src/components/controls/ControlFileHover.vue -->
  2 | <template>
  3 |     <div class="file-hover-card aspect-ratio-box"
  4 |          :class="{ 'is-binary': isGrayScale }"
  5 |          :title="modelValue ? `当前图片: ${modelValue}${isGrayScale ? ' (二值化视图)' : ''}` : '未选择图片'">
  6 |         <div class="card-preview-area">
  7 |             <template v-if="modelValue">
  8 |                 <!-- 只有当有有效 URL 且未报错时才渲染图片 -->
  9 |                 <img v-if="currentDisplayUrl && !hasError"
 10 |                      :src="currentDisplayUrl"
 11 |                      class="preview-image-full"
 12 |                      alt="模板预览"
 13 |                      @error="handleImgError" />
 14 | 
 15 |                 <!-- 图片加载失败时的优雅兜底 -->
 16 |                 <div v-else-if="hasError" class="preview-empty-text error-text">
 17 |                     <span>⚠️ 模板图片加载失败</span>
 18 |                 </div>
 19 | 
 20 |                 <!-- 实时显示二值化提示与参数角标 -->
 21 |                 <div v-if="isGrayScale && !hasError" class="binary-badge">
 22 |                     二值化 (阈值: {{ grayThreshold }})
 23 |                 </div>
 24 |                 <div class="preview-name-badge">{{ modelValue }}</div>
 25 |             </template>
 26 |             <div v-else class="preview-empty-text">
 27 |                 <Image style="width: 14px; height: 14px; margin-bottom: -3px; margin-right: 2px; opacity: 0.6;" />
 28 |                 <span>暂无模板图片（悬停可选择或录入）</span>
 29 |             </div>
 30 |         </div>
 31 | 
 32 |         <div class="hover-action-overlay">
 33 |             <div class="overlay-half left-half" @click.stop="$emit('openBrowser', 'select')">
 34 |                 <span class="action-tip">选择图片</span>
 35 |             </div>
 36 |             <div class="overlay-divider"></div>
 37 |             <div class="overlay-half right-half" @click.stop="$emit('openScreenshot', 'template')">
 38 |                 <span class="action-tip">录入图片</span>
 39 |             </div>
 40 |         </div>
 41 |     </div>
 42 | </template>
 43 | 
 44 | <script setup>
 45 |     import { ref, computed, watch } from 'vue'
 46 |     import { Image } from 'lucide-vue-next'
 47 |     import { useMainStore } from '@/stores'
 48 |     import { visionApi } from '@/api/visionApi'
 49 | 
 50 |     const props = defineProps({
 51 |         config: { type: Object, required: true },
 52 |         modelValue: { type: String, default: '' },
 53 |         imageVersion: { type: Number, default: Date.now() },
 54 |         context: { type: Object, default: () => ({}) }
 55 |     })
 56 | 
 57 |     defineEmits(['update:modelValue', 'openBrowser', 'openScreenshot'])
 58 | 
 59 |     const store = useMainStore()
 60 |     const currentDisplayUrl = ref('')
 61 |     const hasError = ref(false)
 62 |     let timer = null
 63 | 
 64 |     const handleImgError = () => {
 65 |         if (currentDisplayUrl.value) {
 66 |             hasError.value = true
 67 |         }
 68 |     }
 69 | 
 70 |     const isGrayScale = computed(() => !!props.context?.gray_scale)
 71 |     const grayThreshold = computed(() => props.context?.gray_threshold ?? 127)
 72 | 
 73 |     const rawPreviewUrl = computed(() => {
 74 |         if (!props.modelValue) return ''
 75 |         if (props.modelValue.startsWith('http') || props.modelValue.startsWith('data:')) return props.modelValue
 76 |         let cleanName = props.modelValue.replace(/\\/g, '/')
 77 |         if (!/\.(png|jpg|jpeg)$/i.test(cleanName)) {
 78 |             cleanName += '.png'
 79 |         }
 80 |         return `/api/image/thumb?project_path=${encodeURIComponent(store.currentProjectPath || '')}&name=${encodeURIComponent(cleanName)}&t=${props.imageVersion}`
 81 |     })
 82 | 
 83 |     watch(
 84 |         () => [props.modelValue, isGrayScale.value, grayThreshold.value, store.currentProjectPath, props.imageVersion],
 85 |         async ([imgName, grayOn, threshold, projPath]) => {
 86 |             hasError.value = false
 87 | 
 88 |             if (!imgName || !projPath) {
 89 |                 currentDisplayUrl.value = ''
 90 |                 return
 91 |             }
 92 | 
 93 |             if (!grayOn) {
 94 |                 currentDisplayUrl.value = rawPreviewUrl.value
 95 |                 return
 96 |             }
 97 | 
 98 |             if (timer) clearTimeout(timer)
 99 |             timer = setTimeout(async () => {
100 |                 try {
101 |                     const res = await visionApi.testImage(projPath, imgName, true, threshold)
102 |                     if (res && res.image) {
103 |                         currentDisplayUrl.value = res.image
104 |                     } else {
105 |                         currentDisplayUrl.value = rawPreviewUrl.value
106 |                     }
107 |                 } catch (err) {
108 |                     console.error('二值化预览生成失败:', err)
109 |                     currentDisplayUrl.value = rawPreviewUrl.value
110 |                 }
111 |             }, 120)
112 |         },
113 |         { immediate: true }
114 |     )
115 | </script>
116 | 
117 | <style scoped>
118 |     .file-hover-card {
119 |         position: relative;
120 |         width: 100%;
121 |         background: rgba(18, 19, 28, 0.95);
122 |         border: 1px solid var(--el-border-color-light);
123 |         border-radius: var(--app-radius-md, 8px);
124 |         overflow: hidden;
125 |         user-select: none;
126 |         transition: border-color 0.3s, box-shadow 0.3s;
127 |     }
128 | 
129 |         .file-hover-card.is-binary {
130 |             border-color: var(--el-color-success);
131 |             box-shadow: 0 0 8px rgba(103, 194, 58, 0.2);
132 |         }
133 | 
134 |     .aspect-ratio-box {
135 |         aspect-ratio: 4 / 3;
136 |         box-sizing: border-box;
137 |     }
138 | 
139 |     .card-preview-area {
140 |         position: relative;
141 |         width: 100%;
142 |         height: 100%;
143 |         display: flex;
144 |         align-items: center;
145 |         justify-content: center;
146 |         padding: 4px;
147 |         box-sizing: border-box;
148 |     }
149 | 
150 |     .preview-image-full {
151 |         max-width: 100%;
152 |         max-height: 100%;
153 |         width: auto;
154 |         height: auto;
155 |         object-fit: contain;
156 |     }
157 | 
158 |     .binary-badge {
159 |         position: absolute;
160 |         top: 6px;
161 |         right: 6px;
162 |         background: rgba(103, 194, 58, 0.85);
163 |         color: #fff;
164 |         font-size: 10px;
165 |         padding: 2px 6px;
166 |         border-radius: 4px;
167 |         font-weight: bold;
168 |         z-index: 3;
169 |         pointer-events: none;
170 |     }
171 | 
172 |     .preview-name-badge {
173 |         position: absolute;
174 |         bottom: 0;
175 |         left: 0;
176 |         right: 0;
177 |         background: rgba(25, 26, 38, 0.85);
178 |         color: #fff;
179 |         font-size: 10px;
180 |         padding: 2px 6px;
181 |         text-align: center;
182 |         overflow: hidden;
183 |         text-overflow: ellipsis;
184 |         white-space: nowrap;
185 |         z-index: 3;
186 |     }
187 | 
188 |     .preview-empty-text {
189 |         font-size: 11px;
190 |         color: var(--el-text-color-placeholder);
191 |         z-index: 2;
192 |     }
193 | 
194 |     .error-text {
195 |         color: var(--el-color-danger);
196 |     }
197 | 
198 |     .hover-action-overlay {
199 |         position: absolute;
200 |         top: 0;
201 |         left: 0;
202 |         width: 100%;
203 |         height: 100%;
204 |         background: rgba(25, 26, 38, 0.8);
205 |         backdrop-filter: blur(2px);
206 |         display: flex;
207 |         align-items: center;
208 |         opacity: 0;
209 |         pointer-events: none;
210 |         transition: opacity 0.2s ease;
211 |         z-index: 4;
212 |     }
213 | 
214 |     .file-hover-card:hover .hover-action-overlay {
215 |         opacity: 1;
216 |         pointer-events: auto;
217 |     }
218 | 
219 |     .overlay-half {
220 |         flex: 1;
221 |         height: 100%;
222 |         display: flex;
223 |         align-items: center;
224 |         justify-content: center;
225 |         cursor: pointer;
226 |         box-sizing: border-box;
227 |         border: 2px dashed transparent;
228 |         transition: all 0.2s;
229 |     }
230 | 
231 |     .left-half:hover {
232 |         border-color: var(--el-color-primary);
233 |         background: rgba(78, 209, 156, 0.15);
234 |     }
235 | 
236 |     .right-half:hover {
237 |         border-color: #67C23A;
238 |         background: rgba(103, 194, 58, 0.15);
239 |     }
240 | 
241 |     .overlay-divider {
242 |         width: 1px;
243 |         height: 60%;
244 |         background: rgba(255, 255, 255, 0.2);
245 |     }
246 | 
247 |     .action-tip {
248 |         font-size: 12px;
249 |         font-weight: 600;
250 |         color: #fff;
251 |         text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
252 |     }
253 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlNumber.vue

- Extension: .vue
- Language: unknown
- Size: 2571 bytes
- Created: 2026-08-08 21:12:22
- Modified: 2026-08-11 17:29:20

### Code

```unknown
 1 | <!-- frontend/src/components/controls/ControlNumber.vue -->
 2 | <template>
 3 |     <!-- 普通无单位数字输入框 -->
 4 |     <el-input-number v-if="!hasSuffix"
 5 |                      :model-value="modelValue"
 6 |                      :min="config.min !== undefined ? config.min : 0"
 7 |                      :max="config.max !== undefined ? config.max : Infinity"
 8 |                      :step="config.step || (config.type === 'float' ? 0.1 : 1)"
 9 |                      :precision="config.type === 'float' ? 2 : 0"
10 |                      :controls="false"
11 |                      class="pure-number-input"
12 |                      @update:model-value="val => $emit('update:modelValue', val)" />
13 | 
14 |     <!-- 带有单位/后缀的输入框 (由 config.suffix 或 config.unit 驱动) -->
15 |     <el-input v-else
16 |               :model-value="modelValue"
17 |               type="number"
18 |               :min="config.min !== undefined ? config.min : 0"
19 |               :max="config.max !== undefined ? config.max : Infinity"
20 |               class="number-input-with-suffix"
21 |               @update:model-value="val => $emit('update:modelValue', Number(val))">
22 |         <template #suffix>
23 |             <span class="input-unit-suffix">{{ displaySuffix }}</span>
24 |         </template>
25 |     </el-input>
26 | </template>
27 | 
28 | <script setup>
29 |     import { computed } from 'vue'
30 | 
31 |     const props = defineProps({
32 |         config: { type: Object, required: true },
33 |         modelValue: { type: [Number, String], default: 0 },
34 |         label: { type: String, default: '' }
35 |     })
36 |     defineEmits(['update:modelValue'])
37 | 
38 |     const displaySuffix = computed(() => {
39 |         return props.config.suffix || props.config.unit || ''
40 |     })
41 | 
42 |     const hasSuffix = computed(() => {
43 |         return !!displaySuffix.value
44 |     })
45 | </script>
46 | 
47 | <style scoped>
48 |     .pure-number-input {
49 |         width: 100% !important;
50 |     }
51 | 
52 |     .number-input-with-suffix :deep(.el-input__wrapper) {
53 |         background-color: var(--el-fill-color-blank) !important;
54 |         box-shadow: 0 0 0 1px var(--el-border-color-light) inset !important;
55 |         padding-left: 10px !important;
56 |         padding-right: 8px !important;
57 |     }
58 | 
59 |     .number-input-with-suffix :deep(.el-input__inner) {
60 |         text-align: left !important;
61 |         font-size: 12px;
62 |         color: var(--el-text-color-primary);
63 |     }
64 | 
65 |     .input-unit-suffix {
66 |         font-size: 11px;
67 |         font-weight: 600;
68 |         color: var(--el-text-color-secondary);
69 |         margin-left: 2px;
70 |         white-space: nowrap;
71 |         user-select: none;
72 |     }
73 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlRadioGroup.vue

- Extension: .vue
- Language: unknown
- Size: 2215 bytes
- Created: 2026-08-11 17:30:04
- Modified: 2026-08-11 17:30:09

### Code

```unknown
 1 | <!-- frontend/src/components/controls/ControlRadioGroup.vue -->
 2 | <template>
 3 |     <el-radio-group :model-value="modelValue"
 4 |                     class="custom-segmented-radio"
 5 |                     @update:model-value="val => $emit('update:modelValue', val)">
 6 |         <el-radio-button v-for="opt in resolvedOptions"
 7 |                          :key="opt.value"
 8 |                          :value="opt.value">
 9 |             {{ opt.label }}
10 |         </el-radio-button>
11 |     </el-radio-group>
12 | </template>
13 | 
14 | <script setup>
15 | import { computed } from 'vue'
16 | 
17 | const props = defineProps({
18 |   config: { type: Object, required: true },
19 |   modelValue: { required: false },
20 |   context: { type: Object, default: () => ({}) }
21 | })
22 | 
23 | defineEmits(['update:modelValue'])
24 | 
25 | const resolvedOptions = computed(() => {
26 |   const options = props.config.options
27 |   if (typeof options === 'function') {
28 |     try {
29 |       const res = options(props.context, props.modelValue)
30 |       return Array.isArray(res) ? res.map(o => typeof o === 'string' ? { value: o, label: o } : o) : []
31 |     } catch {
32 |       return []
33 |     }
34 |   }
35 |   if (Array.isArray(options)) {
36 |     return options.map(o => typeof o === 'string' ? { value: o, label: o } : o)
37 |   }
38 |   return []
39 | })
40 | </script>
41 | 
42 | <style scoped>
43 |     .custom-segmented-radio {
44 |         display: inline-flex;
45 |         width: 100%;
46 |     }
47 | 
48 |         .custom-segmented-radio :deep(.el-radio-button) {
49 |             flex: 1;
50 |             display: flex;
51 |         }
52 | 
53 |         .custom-segmented-radio :deep(.el-radio-button__inner) {
54 |             width: 100%;
55 |             background-color: var(--el-fill-color-blank) !important;
56 |             border-color: var(--el-border-color-light) !important;
57 |             color: var(--el-text-color-regular) !important;
58 |             font-size: 12px !important;
59 |             padding: 6px 10px !important;
60 |         }
61 | 
62 |         .custom-segmented-radio :deep(.el-radio-button.is-active .el-radio-button__inner) {
63 |             background-color: var(--el-color-primary) !important;
64 |             border-color: var(--el-color-primary) !important;
65 |             color: #fff !important;
66 |             box-shadow: -1px 0 0 0 var(--el-color-primary) !important;
67 |         }
68 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlSelect.vue

- Extension: .vue
- Language: unknown
- Size: 1430 bytes
- Created: 2026-08-08 21:12:29
- Modified: 2026-08-11 17:22:30

### Code

```unknown
 1 | <!-- frontend/src/components/controls/ControlSelect.vue -->
 2 | <template>
 3 |     <el-select :model-value="modelValue"
 4 |                :placeholder="config.label ? `请选择${config.label}` : '请选择...'"
 5 |                style="width: 100%;"
 6 |                @update:model-value="val => $emit('update:modelValue', val)">
 7 |         <el-option v-for="opt in resolvedOptions"
 8 |                    :key="opt.value"
 9 |                    :label="opt.label"
10 |                    :value="opt.value" />
11 |     </el-select>
12 | </template>
13 | 
14 | <script setup>
15 |     import { computed } from 'vue'
16 | 
17 |     const props = defineProps({
18 |         config: { type: Object, required: true },
19 |         modelValue: { required: false },
20 |         context: { type: Object, default: () => ({}) }
21 |     })
22 |     defineEmits(['update:modelValue'])
23 | 
24 |     const resolvedOptions = computed(() => {
25 |         const options = props.config.options
26 |         if (typeof options === 'function') {
27 |             try {
28 |                 const result = options(props.context, props.modelValue)
29 |                 return Array.isArray(result) ? result.map(opt => typeof opt === 'string' ? { value: opt, label: opt } : opt) : []
30 |             } catch {
31 |                 return []
32 |             }
33 |         }
34 |         if (Array.isArray(options)) {
35 |             return options.map(opt => typeof opt === 'string' ? { value: opt, label: opt } : opt)
36 |         }
37 |         return []
38 |     })
39 | </script>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlSlider.vue

- Extension: .vue
- Language: unknown
- Size: 1310 bytes
- Created: 2026-08-11 17:29:52
- Modified: 2026-08-11 17:29:56

### Code

```unknown
 1 | <!-- frontend/src/components/controls/ControlSlider.vue -->
 2 | <template>
 3 |     <div class="control-slider-container">
 4 |         <el-slider :model-value="Number(modelValue)"
 5 |                    :min="config.min !== undefined ? config.min : 0"
 6 |                    :max="config.max !== undefined ? config.max : 100"
 7 |                    :step="config.step || 1"
 8 |                    class="custom-slider"
 9 |                    @update:model-value="val => $emit('update:modelValue', val)" />
10 |         <span v-if="suffix" class="slider-suffix-badge">{{ modelValue }}{{ suffix }}</span>
11 |     </div>
12 | </template>
13 | 
14 | <script setup>
15 | import { computed } from 'vue'
16 | 
17 | const props = defineProps({
18 |   config: { type: Object, required: true },
19 |   modelValue: { type: [Number, String], default: 0 }
20 | })
21 | 
22 | defineEmits(['update:modelValue'])
23 | 
24 | const suffix = computed(() => props.config.suffix || props.config.unit || '')
25 | </script>
26 | 
27 | <style scoped>
28 |     .control-slider-container {
29 |         display: flex;
30 |         align-items: center;
31 |         gap: 12px;
32 |         width: 100%;
33 |     }
34 | 
35 |     .custom-slider {
36 |         flex: 1;
37 |     }
38 | 
39 |     .slider-suffix-badge {
40 |         font-size: 11px;
41 |         font-weight: 600;
42 |         color: var(--el-color-primary);
43 |         min-width: 36px;
44 |         text-align: right;
45 |     }
46 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlString.vue

- Extension: .vue
- Language: unknown
- Size: 451 bytes
- Created: 2026-08-08 21:12:16
- Modified: 2026-08-10 17:15:37

### Code

```unknown
 1 | <!-- frontend/src/components/controls/ControlString.vue -->
 2 | <template>
 3 |     <el-input :model-value="modelValue"
 4 |               :placeholder="config.label || ''"
 5 |               @update:model-value="val => $emit('update:modelValue', val)" />
 6 | </template>
 7 | 
 8 | <script setup>
 9 |     defineProps({
10 |         config: { type: Object, required: true },
11 |         modelValue: { type: String, default: '' }
12 |     })
13 |     defineEmits(['update:modelValue'])
14 | </script>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlSwitch.vue

- Extension: .vue
- Language: unknown
- Size: 875 bytes
- Created: 2026-08-08 21:12:37
- Modified: 2026-08-10 17:15:37

### Code

```unknown
 1 | <!-- frontend/src/components/controls/ControlSwitch.vue -->
 2 | <template>
 3 |     <el-switch :model-value="modelValue"
 4 |                class="custom-fixed-switch"
 5 |                @update:model-value="val => $emit('update:modelValue', val)" />
 6 | </template>
 7 | 
 8 | <script setup>
 9 | defineProps({
10 |   config: { type: Object, required: true },
11 |   modelValue: { type: Boolean, default: false }
12 | })
13 | defineEmits(['update:modelValue'])
14 | </script>
15 | 
16 | <style scoped>
17 |     :deep(.custom-fixed-switch .el-switch__core) {
18 |         background-color: var(--el-fill-color-blank, #181926) !important;
19 |         border-color: var(--el-border-color-light, #313352) !important;
20 |     }
21 | 
22 |     :deep(.custom-fixed-switch.is-checked .el-switch__core) {
23 |         background-color: var(--el-color-primary, #4ed19c) !important;
24 |         border-color: var(--el-color-primary, #4ed19c) !important;
25 |     }
26 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\controls\ControlWindowSelect.vue

- Extension: .vue
- Language: unknown
- Size: 1984 bytes
- Created: 2026-08-08 21:12:44
- Modified: 2026-08-10 17:15:37

### Code

```unknown
 1 | <!-- frontend/src/components/controls/ControlWindowSelect.vue -->
 2 | <template>
 3 |     <el-select :model-value="modelValue"
 4 |                filterable
 5 |                allow-create
 6 |                default-first-option
 7 |                placeholder="下拉选择或手动输入窗口标题"
 8 |                style="width: 100%;"
 9 |                popper-class="window-select-popper"
10 |                :loading="loading"
11 |                @visible-change="onVisibleChange"
12 |                @update:model-value="val => $emit('update:modelValue', val)">
13 |         <el-option v-for="w in windowList"
14 |                    :key="w.hwnd || w.title"
15 |                    :label="w.title"
16 |                    :value="w.title" />
17 |     </el-select>
18 | </template>
19 | 
20 | <script setup>
21 |     import { ref } from 'vue'
22 |     import { workspaceApi } from '@/api/workspaceApi'
23 | 
24 |     defineProps({
25 |         config: { type: Object, default: () => ({}) },
26 |         modelValue: { type: String, default: '' }
27 |     })
28 |     defineEmits(['update:modelValue'])
29 | 
30 |     const windowList = ref([])
31 |     const loading = ref(false)
32 | 
33 |     const fetchWindows = async () => {
34 |         loading.value = true
35 |         try {
36 |             const res = await workspaceApi.getWindows()
37 |             windowList.value = res.windows || []
38 |         } catch (err) {
39 |             console.error('获取窗口列表失败:', err)
40 |         } finally {
41 |             loading.value = false
42 |         }
43 |     }
44 | 
45 |     const onVisibleChange = (visible) => {
46 |         if (visible) {
47 |             fetchWindows()
48 |         }
49 |     }
50 | </script>
51 | 
52 | <!-- ⚡ 仅约束弹出窗口的最大宽度并实现超长文本省略（...），绝不干扰输入框本体样式 -->
53 | <style>
54 |     .window-select-popper {
55 |         max-width: 280px !important;
56 |     }
57 | 
58 |         .window-select-popper .el-select-dropdown__item {
59 |             overflow: hidden !important;
60 |             text-overflow: ellipsis !important;
61 |             white-space: nowrap !important;
62 |         }
63 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\controls\Size2Control.vue

- Extension: .vue
- Language: unknown
- Size: 2542 bytes
- Created: 2026-08-10 16:28:07
- Modified: 2026-08-11 17:26:22

### Code

```unknown
 1 | <!-- frontend/src/components/controls/Size2Control.vue -->
 2 | <template>
 3 |     <div class="size2-control">
 4 |         <div class="input-grid">
 5 |             <div v-for="(item, idx) in fields" :key="item.key" class="field-item">
 6 |                 <span class="field-label">{{ item.label }}</span>
 7 |                 <el-input-number v-model="getValues[idx]"
 8 |                                  :controls="false"
 9 |                                  size="small"
10 |                                  class="compact-num-input"
11 |                                  @change="emitUpdate" />
12 |             </div>
13 |         </div>
14 |     </div>
15 | </template>
16 | 
17 | <script setup>
18 |     import { computed } from 'vue'
19 | 
20 |     const props = defineProps({
21 |         modelValue: { type: Array, default: () => [0, 0] },
22 |         config: { type: Object, default: () => ({}) }
23 |     })
24 | 
25 |     const emit = defineEmits(['update:modelValue', 'change'])
26 | 
27 |     const fields = [
28 |         { key: 'width', label: 'W' },
29 |         { key: 'height', label: 'H' }
30 |     ]
31 | 
32 |     const getValues = computed(() => {
33 |         const arr = Array.isArray(props.modelValue) ? props.modelValue : [0, 0]
34 |         return fields.map((_, i) => Number(arr[i]) || 0)
35 |     })
36 | 
37 |     const emitUpdate = () => {
38 |         const result = [...getValues.value]
39 |         emit('update:modelValue', result)
40 |         emit('change', result)
41 |     }
42 | </script>
43 | 
44 | <style scoped>
45 |     .size2-control {
46 |         width: 100%;
47 |     }
48 | 
49 |     .input-grid {
50 |         display: grid;
51 |         grid-template-columns: repeat(2, 1fr);
52 |         gap: 6px;
53 |         width: 100%;
54 |     }
55 | 
56 |     .field-item {
57 |         display: flex;
58 |         align-items: center;
59 |         background: var(--el-fill-color-blank);
60 |         border: 1px solid var(--el-border-color-light);
61 |         border-radius: 6px;
62 |         padding: 2px 6px;
63 |     }
64 | 
65 |     .field-label {
66 |         font-size: 11px;
67 |         font-weight: 600;
68 |         color: var(--el-text-color-secondary);
69 |         margin-right: 4px;
70 |         user-select: none;
71 |     }
72 | 
73 |     .compact-num-input {
74 |         width: 100% !important;
75 |     }
76 | 
77 |         .compact-num-input :deep(.el-input__wrapper) {
78 |             padding: 0 !important;
79 |             box-shadow: none !important;
80 |             background: transparent !important;
81 |         }
82 | 
83 |         .compact-num-input :deep(.el-input__inner) {
84 |             text-align: center !important;
85 |             font-size: 12px !important;
86 |             font-weight: 600 !important;
87 |             color: var(--el-text-color-primary) !important;
88 |         }
89 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\controls\VariableInputControl.vue

- Extension: .vue
- Language: unknown
- Size: 4083 bytes
- Created: 2026-08-10 15:18:01
- Modified: 2026-08-11 17:23:04

### Code

```unknown
  1 | <!-- frontend/src/components/inspector/controls/VariableInputControl.vue -->
  2 | <template>
  3 |     <div class="variable-input-control">
  4 |         <el-select :model-value="modelValue"
  5 |                    :placeholder="config.placeholder || '选择已有变量或直接输入常数'"
  6 |                    size="small"
  7 |                    filterable
  8 |                    allow-create
  9 |                    default-first-option
 10 |                    clearable
 11 |                    class="var-select-full"
 12 |                    @change="handleSelectChange"
 13 |                    @update:model-value="val => $emit('update:model-value', val)">
 14 |             <el-option v-for="item in availableVariables"
 15 |                        :key="item.value"
 16 |                        :label="item.label"
 17 |                        :value="item.value">
 18 |                 <div class="var-option-item">
 19 |                     <span class="type-badge" :class="`type-${item.type}`">{{ item.typeLabel }}</span>
 20 |                     <span class="var-name">{{ item.value }}</span>
 21 |                 </div>
 22 |             </el-option>
 23 |             <template #empty>
 24 |                 <div class="empty-vars-hint">
 25 |                     <span>暂无预设变量，可直接打字回车输入常数，或在变量面板新建</span>
 26 |                 </div>
 27 |             </template>
 28 |         </el-select>
 29 |     </div>
 30 | </template>
 31 | 
 32 | <script setup>
 33 |     import { computed } from 'vue'
 34 |     import { useMainStore } from '@/stores'
 35 | 
 36 |     const props = defineProps({
 37 |         config: { type: Object, default: () => ({}) },
 38 |         modelValue: { type: [String, Number, Boolean, Array, Object], default: '' },
 39 |         label: { type: String, default: '' },
 40 |         context: { type: Object, default: () => ({}) }
 41 |     })
 42 | 
 43 |     const emit = defineEmits(['update:model-value', 'auto-change-type'])
 44 |     const store = useMainStore()
 45 | 
 46 |     const getVarTypeInfo = (val) => {
 47 |         if (typeof val === 'boolean') return { type: 'boolean', label: 'BOOL' }
 48 |         if (typeof val === 'number') return { type: 'number', label: 'NUM' }
 49 |         if (Array.isArray(val)) return { type: 'list', label: 'LIST' }
 50 |         if (typeof val === 'object' && val !== null) return { type: 'dict', label: 'DICT' }
 51 |         return { type: 'string', label: 'STR' }
 52 |     }
 53 | 
 54 |     const availableVariables = computed(() => {
 55 |         const varsObj = store.blueprint?.variables || {}
 56 |         return Object.keys(varsObj).map(key => {
 57 |             const val = varsObj[key]
 58 |             const typeInfo = getVarTypeInfo(val)
 59 |             return {
 60 |                 value: key,
 61 |                 label: `${key} (${typeInfo.label})`,
 62 |                 type: typeInfo.type,
 63 |                 typeLabel: typeInfo.label
 64 |             }
 65 |         })
 66 |     })
 67 | 
 68 |     const handleSelectChange = (val) => {
 69 |         emit('update:model-value', val)
 70 |         const selectedOpt = availableVariables.value.find(item => item.value === val)
 71 |         if (selectedOpt) {
 72 |             emit('auto-change-type', selectedOpt.type)
 73 |         }
 74 |     }
 75 | </script>
 76 | 
 77 | <style scoped>
 78 |     .variable-input-control {
 79 |         width: 100%;
 80 |     }
 81 | 
 82 |     .var-select-full {
 83 |         width: 100%;
 84 |     }
 85 | 
 86 |     .var-option-item {
 87 |         display: flex;
 88 |         align-items: center;
 89 |         gap: 8px;
 90 |     }
 91 | 
 92 |     .type-badge {
 93 |         font-size: 9px;
 94 |         font-weight: bold;
 95 |         padding: 1px 4px;
 96 |         border-radius: 3px;
 97 |         color: #fff;
 98 |         line-height: 1.2;
 99 |     }
100 | 
101 |     .type-number {
102 |         background: #409eff;
103 |     }
104 | 
105 |     .type-string {
106 |         background: #67c23a;
107 |     }
108 | 
109 |     .type-boolean {
110 |         background: #e6a23c;
111 |     }
112 | 
113 |     .type-list {
114 |         background: #909399;
115 |     }
116 | 
117 |     .type-dict {
118 |         background: #f56c6c;
119 |     }
120 | 
121 |     .var-name {
122 |         font-size: 12px;
123 |         color: var(--el-text-color-primary);
124 |     }
125 | 
126 |     .empty-vars-hint {
127 |         padding: 12px;
128 |         font-size: 11px;
129 |         color: var(--el-text-color-placeholder);
130 |         text-align: center;
131 |         white-space: normal;
132 |         line-height: 1.5;
133 |     }
134 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\inspector\WorkflowInspector.vue

- Extension: .vue
- Language: unknown
- Size: 5839 bytes
- Created: 2026-08-10 13:30:02
- Modified: 2026-08-11 17:46:14

### Code

```unknown
  1 | ﻿<!-- frontend/src/components/inspector/WorkflowInspector.vue -->
  2 | <template>
  3 |     <div class="workflow-inspector-embedded">
  4 |         <!-- 1. 单节点面板 -->
  5 |         <NodeInspectorPanel v-if="targetType === 'node' && currentNode"
  6 |                             :node="currentNode"
  7 |                             @save="triggerSave" />
  8 | 
  9 |         <!-- 2. 多选批量编辑面板 -->
 10 |         <BatchInspectorPanel v-else-if="targetType === 'batch' && selectedNodes.length > 1"
 11 |                              :nodes="selectedNodes"
 12 |                              @save="triggerSave" />
 13 | 
 14 |         <!-- 3. 任务组配置面板 -->
 15 |         <GroupInspectorPanel v-else-if="targetType === 'group' && targetData"
 16 |                              :group="targetData"
 17 |                              @save="triggerSave" />
 18 | 
 19 |         <!-- 4. 空状态提示 -->
 20 |         <div v-else class="inspector-empty-tip">
 21 |             <span>👆 请在画布中点击节点或任务组以查看/编辑属性</span>
 22 |         </div>
 23 |     </div>
 24 | </template>
 25 | 
 26 | <script setup>
 27 |     import { ref, computed, watch } from 'vue'
 28 |     import { useMainStore } from '@/stores'
 29 |     import { blueprintApi } from '@/api/blueprintApi'
 30 |     import NodeInspectorPanel from './panels/NodeInspectorPanel.vue'
 31 |     import BatchInspectorPanel from './panels/BatchInspectorPanel.vue'
 32 |     import GroupInspectorPanel from './panels/GroupInspectorPanel.vue'
 33 | 
 34 |     const store = useMainStore()
 35 |     const currentNode = ref(null)
 36 |     const targetType = ref('node')
 37 |     const targetData = ref(null)
 38 | 
 39 |     const selectedNodes = computed(() => {
 40 |         const ids = store.selectedNodeIds || []
 41 |         const tasks = store.blueprint?.tasks || []
 42 |         let list = []
 43 |         tasks.forEach(t => {
 44 |             (t.nodes || []).forEach(n => {
 45 |                 if (ids.includes(n.node_id)) list.push(n)
 46 |             })
 47 |         })
 48 |         return list
 49 |     })
 50 | 
 51 |     watch(() => [store.selectedNodeIds, store.selectedGroupId], () => {
 52 |         const nodeIds = store.selectedNodeIds || []
 53 |         const tasks = store.blueprint?.tasks || []
 54 | 
 55 |         if (nodeIds.length > 1) {
 56 |             targetType.value = 'batch'
 57 |             targetData.value = null
 58 |             currentNode.value = null
 59 |         } else if (nodeIds.length === 1) {
 60 |             targetType.value = 'node'
 61 |             let foundNode = null
 62 |             for (const task of tasks) {
 63 |                 const n = (task.nodes || []).find(item => item.node_id === nodeIds[0])
 64 |                 if (n) { foundNode = n; break }
 65 |             }
 66 |             if (foundNode) {
 67 |                 const nodeCopy = JSON.parse(JSON.stringify(foundNode))
 68 |                 if (!nodeCopy.params) nodeCopy.params = {}
 69 |                 currentNode.value = nodeCopy
 70 |             }
 71 |         } else if (store.selectedGroupId) {
 72 |             targetType.value = 'group'
 73 |             const t = tasks.find((task, idx) => `group_${task.task_id || idx}` === store.selectedGroupId)
 74 |             if (t) {
 75 |                 targetData.value = {
 76 |                     groupId: store.selectedGroupId,
 77 |                     taskId: t.task_id,
 78 |                     groupName: t.task_name,
 79 |                     loopCount: t.loop_count || 1,
 80 |                     loopInterval: t.loop_interval || 0
 81 |                 }
 82 |                 currentNode.value = null
 83 |             }
 84 |         } else {
 85 |             targetType.value = 'node'
 86 |             currentNode.value = null
 87 |             targetData.value = null
 88 |         }
 89 |     }, { immediate: true, deep: true })
 90 | 
 91 |     const triggerSave = async () => {
 92 |         try {
 93 |             if (targetType.value === 'node' && currentNode.value) {
 94 |                 const tasks = store.blueprint?.tasks || []
 95 |                 for (const task of tasks) {
 96 |                     if (task.nodes) {
 97 |                         const idx = task.nodes.findIndex(n => n.node_id === currentNode.value.node_id)
 98 |                         if (idx > -1) {
 99 |                             currentNode.value.loop_count = Number(currentNode.value.loop_count) || 1
100 |                             currentNode.value.delay_before = Number(currentNode.value.delay_before) || 0
101 |                             task.nodes[idx] = JSON.parse(JSON.stringify(currentNode.value))
102 |                             break
103 |                         }
104 |                     }
105 |                 }
106 |             } else if (targetType.value === 'group' && targetData.value) {
107 |                 targetData.value.loopCount = Number(targetData.value.loopCount) || 1
108 |                 targetData.value.loopInterval = Number(targetData.value.loopInterval) || 0
109 |                 const groupTask = store.blueprint?.tasks?.find(t => t.task_id === targetData.value.taskId || `group_${t.task_id}` === targetData.value.groupId)
110 |                 if (groupTask) {
111 |                     groupTask.task_name = targetData.value.groupName
112 |                     groupTask.loop_count = targetData.value.loopCount
113 |                     groupTask.loop_interval = targetData.value.loopInterval
114 |                 }
115 |             }
116 |             await blueprintApi.saveBlueprint(store.currentProjectPath, store.blueprint)
117 |         } catch (err) {
118 |             console.error('保存节点配置失败:', err)
119 |         }
120 |     }
121 | </script>
122 | 
123 | <style scoped>
124 |     .workflow-inspector-embedded {
125 |         width: 100%;
126 |         height: 100%;
127 |         background: rgba(38, 40, 61, 0.95);
128 |         display: flex;
129 |         flex-direction: column;
130 |         user-select: none;
131 |         overflow: hidden;
132 |         box-sizing: border-box;
133 |     }
134 | 
135 |     .inspector-empty-tip {
136 |         flex: 1;
137 |         display: flex;
138 |         align-items: center;
139 |         justify-content: center;
140 |         padding: 20px;
141 |         text-align: center;
142 |         font-size: 12px;
143 |         color: var(--el-text-color-placeholder);
144 |     }
145 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\inspector\panels\BatchInspectorPanel.vue

- Extension: .vue
- Language: unknown
- Size: 8951 bytes
- Created: 2026-08-10 12:32:00
- Modified: 2026-08-11 17:45:48

### Code

```unknown
  1 | ﻿<!-- frontend/src/components/inspector/panels/BatchInspectorPanel.vue -->
  2 | <template>
  3 |     <div class="panel-layout-root">
  4 |         <!-- 1. 顶部 Files 图标 + 100% 还原单选视觉样式的标题 Input -->
  5 |         <div class="inspector-fixed-header">
  6 |             <div class="node-title-box">
  7 |                 <div class="node-type-icon-badge" title="批量编辑">
  8 |                     <Files class="inspector-type-svg" />
  9 |                 </div>
 10 |                 <el-input :model-value="`批量编辑已选中的 ${nodes.length} 个节点`"
 11 |                           readonly
 12 |                           size="default"
 13 |                           class="node-name-input batch-title-input" />
 14 |             </div>
 15 |         </div>
 16 | 
 17 |         <!-- 2. 中间共有属性渲染区 -->
 18 |         <div class="inspector-scrollable-body">
 19 |             <div class="params-container">
 20 |                 <template v-for="(config, paramName) in commonParams" :key="paramName">
 21 |                     <div v-if="!['region_value', 'gray_threshold', 'on_success', 'on_failure', 'candidates'].includes(paramName)" class="param-item">
 22 |                         <ParamRenderer :config="config"
 23 |                                        :value="getCommonParamValue(paramName)"
 24 |                                        :label="config.label || paramName"
 25 |                                        :context="{}"
 26 |                                        @update="val => handleBatchParamUpdate(paramName, val)"
 27 |                                        @auto-change-type="inferredType => handleBatchParamUpdate('var_type', inferredType)" />
 28 |                     </div>
 29 |                 </template>
 30 | 
 31 |                 <div v-if="Object.keys(commonParams).length === 0" class="inspector-empty-tip">
 32 |                     <span>所选节点无公共可配置属性</span>
 33 |                 </div>
 34 |             </div>
 35 |         </div>
 36 | 
 37 |         <!-- 3. 底部批量延迟/循环次数 -->
 38 |         <div class="inspector-fixed-footer">
 39 |             <div class="footer-inline-container">
 40 |                 <div class="footer-setting-group">
 41 |                     <span class="footer-label">延迟</span>
 42 |                     <el-input v-model.number="batchDelay" size="small" class="pure-compact-input" />
 43 |                     <span class="footer-unit">ms</span>
 44 |                 </div>
 45 |                 <div class="footer-setting-group">
 46 |                     <span class="footer-label">循环</span>
 47 |                     <el-input v-model.number="batchLoop" size="small" class="pure-compact-input" />
 48 |                     <span class="footer-unit">次</span>
 49 |                 </div>
 50 |             </div>
 51 |         </div>
 52 |     </div>
 53 | </template>
 54 | 
 55 | <script setup>
 56 |     import { computed } from 'vue'
 57 |     import { useMainStore } from '@/stores'
 58 |     import ParamRenderer from '@/components/ParamRenderer.vue'
 59 |     import { Files } from 'lucide-vue-next'
 60 | 
 61 |     const props = defineProps({
 62 |         nodes: { type: Array, default: () => [] }
 63 |     })
 64 |     const emit = defineEmits(['save'])
 65 |     const store = useMainStore()
 66 | 
 67 |     const commonParams = computed(() => {
 68 |         if (!props.nodes || props.nodes.length === 0) return {}
 69 |         const paramDefsList = props.nodes.map(n => store.paramsDefinitions[n.node_type]?.params || {})
 70 |         if (paramDefsList.length === 0) return {}
 71 | 
 72 |         const firstDefs = paramDefsList[0]
 73 |         const common = {}
 74 |         for (const [key, config] of Object.entries(firstDefs)) {
 75 |             const isCommon = paramDefsList.every(defs => Object.prototype.hasOwnProperty.call(defs, key))
 76 |             if (isCommon) common[key] = config
 77 |         }
 78 |         return common
 79 |     })
 80 | 
 81 |     const getCommonParamValue = (paramName) => {
 82 |         if (!props.nodes || props.nodes.length === 0) return ''
 83 |         const firstVal = props.nodes[0].params?.[paramName]
 84 |         const allSame = props.nodes.every(n => JSON.stringify(n.params?.[paramName]) === JSON.stringify(firstVal))
 85 |         return allSame ? firstVal : ''
 86 |     }
 87 | 
 88 |     const handleBatchParamUpdate = (paramName, value) => {
 89 |         const ids = props.nodes.map(n => n.node_id)
 90 |         store.blueprint?.tasks?.forEach(t => {
 91 |             (t.nodes || []).forEach(n => {
 92 |                 if (ids.includes(n.node_id)) {
 93 |                     if (!n.params) n.params = {}
 94 |                     n.params[paramName] = value
 95 |                 }
 96 |             })
 97 |         })
 98 |         emit('save')
 99 |     }
100 | 
101 |     const batchDelay = computed({
102 |         get: () => {
103 |             if (!props.nodes || props.nodes.length === 0) return 200
104 |             const firstVal = props.nodes[0].delay_before ?? 200
105 |             const allSame = props.nodes.every(n => (n.delay_before ?? 200) === firstVal)
106 |             return allSame ? firstVal : ''
107 |         },
108 |         set: (val) => {
109 |             const num = Number(val) || 0
110 |             const ids = props.nodes.map(n => n.node_id)
111 |             store.blueprint?.tasks?.forEach(t => {
112 |                 (t.nodes || []).forEach(n => {
113 |                     if (ids.includes(n.node_id)) n.delay_before = num
114 |                 })
115 |             })
116 |             emit('save')
117 |         }
118 |     })
119 | 
120 |     const batchLoop = computed({
121 |         get: () => {
122 |             if (!props.nodes || props.nodes.length === 0) return 1
123 |             const firstVal = props.nodes[0].loop_count ?? 1
124 |             const allSame = props.nodes.every(n => (n.loop_count ?? 1) === firstVal)
125 |             return allSame ? firstVal : ''
126 |         },
127 |         set: (val) => {
128 |             const num = Number(val) || 1
129 |             const ids = props.nodes.map(n => n.node_id)
130 |             store.blueprint?.tasks?.forEach(t => {
131 |                 (t.nodes || []).forEach(n => {
132 |                     if (ids.includes(n.node_id)) n.loop_count = num
133 |                 })
134 |             })
135 |             emit('save')
136 |         }
137 |     })
138 | </script>
139 | 
140 | <style scoped>
141 |     .panel-layout-root {
142 |         width: 100%;
143 |         height: 100%;
144 |         display: flex;
145 |         flex-direction: column;
146 |     }
147 | 
148 |     .inspector-fixed-header {
149 |         padding: 12px 14px;
150 |         background: rgba(25, 26, 38, 0.95);
151 |         border-bottom: 1px solid var(--el-border-color-light);
152 |         flex-shrink: 0;
153 |     }
154 | 
155 |     .node-title-box {
156 |         display: flex;
157 |         align-items: center;
158 |         gap: 10px;
159 |     }
160 | 
161 |     .node-type-icon-badge {
162 |         width: 32px;
163 |         height: 32px;
164 |         background: rgba(78, 209, 156, 0.1);
165 |         border: 1px solid rgba(78, 209, 156, 0.3);
166 |         border-radius: 8px;
167 |         display: flex;
168 |         align-items: center;
169 |         justify-content: center;
170 |         flex-shrink: 0;
171 |     }
172 | 
173 |     .inspector-type-svg {
174 |         width: 18px;
175 |         height: 18px;
176 |         color: var(--el-color-primary);
177 |     }
178 | 
179 |     .batch-title-input {
180 |         flex: 1;
181 |     }
182 | 
183 |         .batch-title-input :deep(.el-input__wrapper) {
184 |             cursor: default !important;
185 |             background-color: transparent !important;
186 |             box-shadow: none !important;
187 |             border: none !important;
188 |             padding-left: 0 !important;
189 |         }
190 | 
191 |         .batch-title-input :deep(.el-input__inner) {
192 |             cursor: default !important;
193 |             font-size: 13px !important;
194 |             font-weight: 600 !important;
195 |             color: var(--el-text-color-primary) !important;
196 |         }
197 | 
198 |     .inspector-scrollable-body {
199 |         flex: 1;
200 |         padding: 12px 14px;
201 |         overflow-y: auto;
202 |         overscroll-behavior: contain;
203 |     }
204 | 
205 |     .params-container {
206 |         display: flex;
207 |         flex-direction: column;
208 |         gap: 12px;
209 |     }
210 | 
211 |     .param-item {
212 |         display: flex;
213 |         flex-direction: column;
214 |         gap: 4px;
215 |     }
216 | 
217 |     .inspector-empty-tip {
218 |         padding: 30px 0;
219 |         text-align: center;
220 |         font-size: 12px;
221 |         color: var(--el-text-color-placeholder);
222 |     }
223 | 
224 |     .inspector-fixed-footer {
225 |         padding: 10px 14px;
226 |         background: rgba(25, 26, 38, 0.95);
227 |         border-top: 1px solid var(--el-border-color-light);
228 |         flex-shrink: 0;
229 |     }
230 | 
231 |     .footer-inline-container {
232 |         display: flex;
233 |         align-items: center;
234 |         justify-content: space-between;
235 |     }
236 | 
237 |     .footer-setting-group {
238 |         display: flex;
239 |         align-items: center;
240 |         gap: 6px;
241 |         font-size: 12px;
242 |         color: var(--el-text-color-regular);
243 |     }
244 | 
245 |     .footer-label {
246 |         font-weight: 600;
247 |         color: var(--el-text-color-primary);
248 |     }
249 | 
250 |     .footer-unit {
251 |         font-size: 11px;
252 |         color: var(--el-text-color-secondary);
253 |     }
254 | 
255 |     .pure-compact-input {
256 |         width: 60px !important;
257 |     }
258 | 
259 |         .pure-compact-input :deep(.el-input__wrapper) {
260 |             padding-left: 4px !important;
261 |             padding-right: 4px !important;
262 |             background-color: var(--el-fill-color-blank) !important;
263 |         }
264 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\inspector\panels\GroupInspectorPanel.vue

- Extension: .vue
- Language: unknown
- Size: 4379 bytes
- Created: 2026-08-10 12:31:55
- Modified: 2026-08-11 17:46:03

### Code

```unknown
  1 | ﻿<!-- frontend/src/components/inspector/panels/GroupInspectorPanel.vue -->
  2 | <template>
  3 |     <div class="panel-layout-root">
  4 |         <!-- 1. 顶部 Folder 图标 + 组名称 -->
  5 |         <div class="inspector-fixed-header">
  6 |             <div class="node-title-box">
  7 |                 <div class="node-type-icon-badge" title="任务组配置">
  8 |                     <Folder class="inspector-type-svg" />
  9 |                 </div>
 10 |                 <el-input v-model="group.groupName" size="default" class="node-name-input" placeholder="请输入任务组名称" @change="handleSave" />
 11 |             </div>
 12 |         </div>
 13 | 
 14 |         <!-- 2. 中间提示占位 -->
 15 |         <div class="inspector-scrollable-body">
 16 |             <div class="inspector-empty-tip">
 17 |                 <span>📁 当前配置适用于任务组 [{{ group.groupName }}]</span>
 18 |             </div>
 19 |         </div>
 20 | 
 21 |         <!-- 3. 底部组循环间隔/循环次数 -->
 22 |         <div class="inspector-fixed-footer">
 23 |             <div class="footer-inline-container">
 24 |                 <div class="footer-setting-group">
 25 |                     <span class="footer-label">循环间隔</span>
 26 |                     <el-input v-model.number="group.loopInterval" size="small" class="pure-compact-input" @change="handleSave" />
 27 |                     <span class="footer-unit">ms</span>
 28 |                 </div>
 29 |                 <div class="footer-setting-group">
 30 |                     <span class="footer-label">循环</span>
 31 |                     <el-input v-model.number="group.loopCount" size="small" class="pure-compact-input" @change="handleSave" />
 32 |                     <span class="footer-unit">次</span>
 33 |                 </div>
 34 |             </div>
 35 |         </div>
 36 |     </div>
 37 | </template>
 38 | 
 39 | <script setup>
 40 |     import { Folder } from 'lucide-vue-next'
 41 | 
 42 |     defineProps({
 43 |         group: { type: Object, required: true }
 44 |     })
 45 |     const emit = defineEmits(['save'])
 46 |     const handleSave = () => emit('save')
 47 | </script>
 48 | 
 49 | <style scoped>
 50 |     .panel-layout-root {
 51 |         width: 100%;
 52 |         height: 100%;
 53 |         display: flex;
 54 |         flex-direction: column;
 55 |     }
 56 | 
 57 |     .inspector-fixed-header {
 58 |         padding: 12px 14px;
 59 |         background: rgba(25, 26, 38, 0.95);
 60 |         border-bottom: 1px solid var(--el-border-color-light);
 61 |         flex-shrink: 0;
 62 |     }
 63 | 
 64 |     .inspector-scrollable-body {
 65 |         flex: 1;
 66 |         padding: 12px 14px;
 67 |         overflow-y: auto;
 68 |         overscroll-behavior: contain;
 69 |         display: flex;
 70 |     }
 71 | 
 72 |     .inspector-fixed-footer {
 73 |         padding: 10px 14px;
 74 |         background: rgba(25, 26, 38, 0.95);
 75 |         border-top: 1px solid var(--el-border-color-light);
 76 |         flex-shrink: 0;
 77 |     }
 78 | 
 79 |     .node-title-box {
 80 |         display: flex;
 81 |         align-items: center;
 82 |         gap: 10px;
 83 |     }
 84 | 
 85 |     .node-type-icon-badge {
 86 |         width: 32px;
 87 |         height: 32px;
 88 |         background: rgba(78, 209, 156, 0.1);
 89 |         border: 1px solid rgba(78, 209, 156, 0.3);
 90 |         border-radius: 8px;
 91 |         display: flex;
 92 |         align-items: center;
 93 |         justify-content: center;
 94 |         flex-shrink: 0;
 95 |     }
 96 | 
 97 |     .inspector-type-svg {
 98 |         width: 18px;
 99 |         height: 18px;
100 |         color: var(--el-color-primary);
101 |     }
102 | 
103 |     .inspector-empty-tip {
104 |         flex: 1;
105 |         display: flex;
106 |         align-items: center;
107 |         justify-content: center;
108 |         padding: 20px;
109 |         text-align: center;
110 |         font-size: 12px;
111 |         color: var(--el-text-color-placeholder);
112 |     }
113 | 
114 |     .footer-inline-container {
115 |         display: flex;
116 |         align-items: center;
117 |         justify-content: space-between;
118 |     }
119 | 
120 |     .footer-setting-group {
121 |         display: flex;
122 |         align-items: center;
123 |         gap: 6px;
124 |         font-size: 12px;
125 |         color: var(--el-text-color-regular);
126 |     }
127 | 
128 |     .footer-label {
129 |         font-weight: 600;
130 |         color: var(--el-text-color-primary);
131 |     }
132 | 
133 |     .footer-unit {
134 |         font-size: 11px;
135 |         color: var(--el-text-color-secondary);
136 |     }
137 | 
138 |     .pure-compact-input {
139 |         width: 60px !important;
140 |     }
141 | 
142 |         .pure-compact-input :deep(.el-input__wrapper) {
143 |             padding-left: 4px !important;
144 |             padding-right: 4px !important;
145 |             background-color: var(--el-fill-color-blank) !important;
146 |         }
147 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\inspector\panels\NodeInspectorPanel.vue

- Extension: .vue
- Language: unknown
- Size: 13113 bytes
- Created: 2026-08-10 12:31:49
- Modified: 2026-08-11 17:45:13

### Code

```unknown
  1 | ﻿<!-- frontend/src/components/inspector/panels/NodeInspectorPanel.vue -->
  2 | <template>
  3 |     <div class="panel-layout-root">
  4 |         <!-- 1. 顶部固定标题 -->
  5 |         <div class="inspector-fixed-header">
  6 |             <div class="node-title-box">
  7 |                 <div class="node-type-icon-badge" :title="nodeTypeLabel">
  8 |                     <component :is="getNodeIcon(node.node_type)" class="inspector-type-svg" />
  9 |                 </div>
 10 |                 <el-input v-model="node.node_name" size="default" class="node-name-input" placeholder="请输入节点名称" @change="handleSave" />
 11 |             </div>
 12 |         </div>
 13 | 
 14 |         <!-- 2. 中间滚动参数区 -->
 15 |         <div class="inspector-scrollable-body">
 16 |             <div class="params-container">
 17 |                 <!-- ⚡ OCR 专属: 顶部图片下方的实时识字高亮结果框 -->
 18 |                 <div v-if="node.node_type === 'ocr_recognition'" class="ocr-live-result-card">
 19 |                     <div class="result-header">
 20 |                         <span>🔤 当前视角识别文字结果</span>
 21 |                         <el-button size="small" type="primary" link :loading="previewLoading" @click="fetchOcrText">
 22 |                             <RefreshCcw style="width: 12px; height: 12px; margin-right: 2px;" :class="{ 'is-spinning': previewLoading }" />
 23 |                             测试识别
 24 |                         </el-button>
 25 |                     </div>
 26 |                     <div class="result-text-box" :class="{ 'is-empty': !previewText }">
 27 |                         {{ previewText || '(暂未识别到文本，拖动灰度滑条或点击测试)' }}
 28 |                     </div>
 29 |                 </div>
 30 | 
 31 |                 <!-- ⚡ 纯 Schema 自动分发表单：依次渲染节点参数 -->
 32 |                 <template v-for="(config, paramName) in allParams" :key="paramName + (node ? node.node_id : '')">
 33 |                     <!-- 灰度阈值滑块定制优化 (支持实时二值化黑白预览与防抖测试) -->
 34 |                     <div v-if="paramName === 'gray_threshold' && node.params.gray_scale" class="param-item slider-box">
 35 |                         <div class="slider-header">
 36 |                             <span>二值化灰度阈值: <strong>{{ node.params.gray_threshold ?? 127 }}</strong></span>
 37 |                             <span class="slider-tip">(向左增强浅色，向右过滤背景)</span>
 38 |                         </div>
 39 |                         <el-slider v-model="node.params.gray_threshold"
 40 |                                    :min="0"
 41 |                                    :max="255"
 42 |                                    :step="1"
 43 |                                    @input="val => handleParamUpdate('gray_threshold', val)"
 44 |                                    @change="val => handleParamUpdate('gray_threshold', val)" />
 45 |                     </div>
 46 | 
 47 |                     <!-- 基础通用参数渲染网关 -->
 48 |                     <div v-else-if="!['gray_threshold', 'on_success', 'on_failure'].includes(paramName)" class="param-item">
 49 |                         <ParamRenderer :config="config"
 50 |                                        :value="node.params[paramName]"
 51 |                                        :label="config.label || paramName"
 52 |                                        :context="node.params"
 53 |                                        @update="val => handleParamUpdate(paramName, val)"
 54 |                                        @auto-change-type="handleAutoChangeType" />
 55 |                     </div>
 56 |                 </template>
 57 |             </div>
 58 |         </div>
 59 | 
 60 |         <!-- 3. 底部固定延时/循环 -->
 61 |         <div class="inspector-fixed-footer">
 62 |             <div class="footer-inline-container">
 63 |                 <div class="footer-setting-group">
 64 |                     <span class="footer-label">延迟</span>
 65 |                     <el-input v-model.number="node.delay_before" size="small" class="pure-compact-input" @change="handleSave" />
 66 |                     <span class="footer-unit">ms</span>
 67 |                 </div>
 68 |                 <div class="footer-setting-group">
 69 |                     <span class="footer-label">循环</span>
 70 |                     <el-input v-model.number="node.loop_count" size="small" class="pure-compact-input" @change="handleSave" />
 71 |                     <span class="footer-unit">次</span>
 72 |                 </div>
 73 |             </div>
 74 |         </div>
 75 |     </div>
 76 | </template>
 77 | 
 78 | <script setup>
 79 |     import { ref, computed, watch } from 'vue'
 80 |     import { useMainStore } from '@/stores'
 81 |     import { visionApi } from '@/api/visionApi'
 82 |     import ParamRenderer from '@/components/ParamRenderer.vue'
 83 |     import {
 84 |         MousePointerClick, Clock, Image, ScanText, GitBranch,
 85 |         SearchCheck, Binary, ListOrdered, FileCode, RefreshCcw
 86 |     } from 'lucide-vue-next'
 87 | 
 88 |     const props = defineProps({
 89 |         node: { type: Object, required: true }
 90 |     })
 91 |     const emit = defineEmits(['save'])
 92 |     const store = useMainStore()
 93 | 
 94 |     const previewLoading = ref(false)
 95 |     const previewText = ref('')
 96 |     const originalRecordedRegion = ref(null)
 97 |     const imageVersion = ref(Date.now())
 98 |     let isSyncingRecorded = false
 99 |     let ocrTimer = null
100 | 
101 |     const nodeIconComponentMap = {
102 |         click: MousePointerClick,
103 |         wait: Clock,
104 |         image_recognition: Image,
105 |         ocr_recognition: ScanText,
106 |         branch: GitBranch,
107 |         logic_check: SearchCheck,
108 |         variable_op: Binary,
109 |         log: ListOrdered,
110 |         script_call: FileCode
111 |     }
112 |     const getNodeIcon = (type) => nodeIconComponentMap[type] || FileCode
113 | 
114 |     const nodeTypeLabel = computed(() => store.paramsDefinitions[props.node?.node_type]?.label || props.node?.node_type)
115 |     const allParams = computed(() => store.paramsDefinitions[props.node?.node_type]?.params || {})
116 | 
117 |     // ⚡ OCR 文本测试识别方法
118 |     const fetchOcrText = async () => {
119 |         if (!props.node || props.node.node_type !== 'ocr_recognition') return
120 |         previewLoading.value = true
121 |         try {
122 |             const res = await visionApi.testOcr(
123 |                 store.currentProjectPath,
124 |                 props.node.params.region_value || [0, 0, 0, 0],
125 |                 props.node.params.gray_scale ?? true,
126 |                 props.node.params.gray_threshold ?? 127,
127 |                 props.node.params.image_source || ''
128 |             )
129 |             if (res) {
130 |                 previewText.value = res.text || ''
131 |             }
132 |         } catch (err) {
133 |             console.warn('OCR 测试失败', err)
134 |         } finally {
135 |             previewLoading.value = false
136 |         }
137 |     }
138 | 
139 |     const syncRecordedRegion = async () => {
140 |         if (!props.node || !store.currentProjectPath) return
141 |         const rawTemplateName = props.node.params.image_source
142 |         if (!rawTemplateName) return
143 | 
144 |         isSyncingRecorded = true
145 |         try {
146 |             const regions = await visionApi.getRegions(store.currentProjectPath)
147 |             const cleanName = rawTemplateName.replace(/\.png$/i, '').replace(/\\/g, '/')
148 |             const fileNameOnly = cleanName.split('/').pop()
149 |             const rect = regions[rawTemplateName] || regions[cleanName] || regions[fileNameOnly] || regions[`${cleanName}.png`]
150 |             if (rect && Array.isArray(rect) && rect.length === 4) {
151 |                 props.node.params.region_value = [...rect]
152 |                 originalRecordedRegion.value = [...rect]
153 |             }
154 |         } catch (err) {
155 |             console.error('获取区域配置失败', err)
156 |         } finally {
157 |             setTimeout(() => { isSyncingRecorded = false }, 300)
158 |         }
159 |     }
160 | 
161 |     watch(() => props.node?.node_id, () => {
162 |         if (props.node?.params?.region_type === 'recorded') {
163 |             syncRecordedRegion()
164 |         }
165 |         previewText.value = ''
166 |         if (props.node?.node_type === 'ocr_recognition') {
167 |             fetchOcrText()
168 |         }
169 |     }, { immediate: true })
170 | 
171 |     const handleAutoChangeType = (inferredType) => {
172 |         if (inferredType && props.node && props.node.params) {
173 |             props.node.params.var_type = inferredType
174 |             handleSave()
175 |         }
176 |     }
177 | 
178 |     const handleParamUpdate = (paramName, value) => {
179 |         if (paramName === 'region_value' && props.node.params.region_type === 'recorded' && !isSyncingRecorded) {
180 |             if (originalRecordedRegion.value && JSON.stringify(value) !== JSON.stringify(originalRecordedRegion.value)) {
181 |                 props.node.params.region_type = 'custom'
182 |             }
183 |         }
184 |         props.node.params[paramName] = value
185 |         props.node.params = { ...props.node.params }
186 | 
187 |         if (paramName === 'region_type' && value === 'recorded') syncRecordedRegion()
188 |         if (paramName === 'image_source' && props.node.params.region_type === 'recorded') syncRecordedRegion()
189 | 
190 |         if (['image_source', 'gray_scale', 'gray_threshold'].includes(paramName)) {
191 |             imageVersion.value = Date.now()
192 |             if (props.node?.node_type === 'ocr_recognition') {
193 |                 if (ocrTimer) clearTimeout(ocrTimer)
194 |                 ocrTimer = setTimeout(fetchOcrText, 200)
195 |             }
196 |         }
197 |         handleSave()
198 |     }
199 | 
200 |     const handleSave = () => emit('save')
201 | </script>
202 | 
203 | <style scoped>
204 |     .panel-layout-root {
205 |         width: 100%;
206 |         height: 100%;
207 |         display: flex;
208 |         flex-direction: column;
209 |     }
210 | 
211 |     .inspector-fixed-header {
212 |         padding: 12px 14px;
213 |         background: rgba(25, 26, 38, 0.95);
214 |         border-bottom: 1px solid var(--el-border-color-light);
215 |         flex-shrink: 0;
216 |     }
217 | 
218 |     .inspector-scrollable-body {
219 |         flex: 1;
220 |         padding: 12px 14px;
221 |         overflow-y: auto;
222 |         overscroll-behavior: contain;
223 |     }
224 | 
225 |     .inspector-fixed-footer {
226 |         padding: 10px 14px;
227 |         background: rgba(25, 26, 38, 0.95);
228 |         border-top: 1px solid var(--el-border-color-light);
229 |         flex-shrink: 0;
230 |     }
231 | 
232 |     .node-title-box {
233 |         display: flex;
234 |         align-items: center;
235 |         gap: 10px;
236 |     }
237 | 
238 |     .node-type-icon-badge {
239 |         width: 32px;
240 |         height: 32px;
241 |         background: rgba(78, 209, 156, 0.1);
242 |         border: 1px solid rgba(78, 209, 156, 0.3);
243 |         border-radius: 8px;
244 |         display: flex;
245 |         align-items: center;
246 |         justify-content: center;
247 |         flex-shrink: 0;
248 |     }
249 | 
250 |     .inspector-type-svg {
251 |         width: 18px;
252 |         height: 18px;
253 |         color: var(--el-color-primary);
254 |     }
255 | 
256 |     .params-container {
257 |         display: flex;
258 |         flex-direction: column;
259 |         gap: 12px;
260 |     }
261 | 
262 |     .param-item {
263 |         display: flex;
264 |         flex-direction: column;
265 |         gap: 4px;
266 |     }
267 | 
268 |     .ocr-live-result-card {
269 |         background: rgba(103, 194, 58, 0.08);
270 |         border: 1px solid rgba(103, 194, 58, 0.3);
271 |         border-radius: 8px;
272 |         padding: 10px 12px;
273 |         margin-bottom: 4px;
274 |     }
275 | 
276 |     .result-header {
277 |         display: flex;
278 |         justify-content: space-between;
279 |         align-items: center;
280 |         font-size: 11px;
281 |         font-weight: bold;
282 |         color: var(--el-color-success);
283 |         margin-bottom: 6px;
284 |     }
285 | 
286 |     .result-text-box {
287 |         font-size: 15px;
288 |         font-weight: bold;
289 |         color: var(--el-color-success);
290 |         word-break: break-all;
291 |         line-height: 1.4;
292 |     }
293 | 
294 |         .result-text-box.is-empty {
295 |             font-size: 11px;
296 |             font-weight: normal;
297 |             color: var(--el-text-color-placeholder);
298 |         }
299 | 
300 |     .slider-box {
301 |         background: var(--el-fill-color-blank);
302 |         padding: 10px 12px;
303 |         border-radius: 8px;
304 |         border: 1px solid var(--el-border-color-light);
305 |     }
306 | 
307 |     .slider-header {
308 |         display: flex;
309 |         justify-content: space-between;
310 |         font-size: 12px;
311 |         color: var(--el-text-color-primary);
312 |         margin-bottom: 4px;
313 |     }
314 | 
315 |     .slider-tip {
316 |         color: var(--el-text-color-secondary);
317 |         font-size: 11px;
318 |     }
319 | 
320 |     .footer-inline-container {
321 |         display: flex;
322 |         align-items: center;
323 |         justify-content: space-between;
324 |     }
325 | 
326 |     .footer-setting-group {
327 |         display: flex;
328 |         align-items: center;
329 |         gap: 6px;
330 |         font-size: 12px;
331 |         color: var(--el-text-color-regular);
332 |     }
333 | 
334 |     .footer-label {
335 |         font-weight: 600;
336 |         color: var(--el-text-color-primary);
337 |     }
338 | 
339 |     .footer-unit {
340 |         font-size: 11px;
341 |         color: var(--el-text-color-secondary);
342 |     }
343 | 
344 |     .pure-compact-input {
345 |         width: 60px !important;
346 |     }
347 | 
348 |         .pure-compact-input :deep(.el-input__wrapper) {
349 |             padding-left: 4px !important;
350 |             padding-right: 4px !important;
351 |             background-color: var(--el-fill-color-blank) !important;
352 |         }
353 | 
354 |     .is-spinning {
355 |         animation: spin 1s linear infinite;
356 |     }
357 | 
358 |     @keyframes spin {
359 |         100% {
360 |             transform: rotate(360deg);
361 |         }
362 |     }
363 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\panels\GlobalVariablesPanel.vue

- Extension: .vue
- Language: unknown
- Size: 29582 bytes
- Created: 2026-08-10 12:09:33
- Modified: 2026-08-11 18:45:37

### Code

```unknown
  1 | <!-- frontend/src/components/panels/GlobalVariablesPanel.vue -->
  2 | <template>
  3 |     <div class="global-vars-panel">
  4 |         <div class="accordion-container">
  5 | 
  6 |             <!-- 1. 第一行：用户自定义全局变量 -->
  7 |             <div class="accordion-item" :class="{ 'is-expanded': expandedSection === 'user' }">
  8 |                 <div class="accordion-header" @click="toggleSection('user')">
  9 |                     <div class="header-left">
 10 |                         <span class="header-title">用户自定义全局变量</span>
 11 |                         <span class="tab-badge">{{ userVarList.length }}</span>
 12 |                     </div>
 13 |                     <ChevronDown class="arrow-icon" :class="{ 'is-rotated': expandedSection === 'user' }" />
 14 |                 </div>
 15 | 
 16 |                 <div v-show="expandedSection === 'user'" class="accordion-content">
 17 |                     <!-- 工具栏：新建变量弹窗触发与一键清理 -->
 18 |                     <div class="vars-toolbar">
 19 |                         <el-button size="small" type="primary" class="pure-btn" @click="openCreateDialog">
 20 |                             <Plus class="btn-icon" />
 21 |                             <span>新建变量</span>
 22 |                         </el-button>
 23 | 
 24 |                         <el-button size="small"
 25 |                                    type="danger"
 26 |                                    plain
 27 |                                    class="pure-btn"
 28 |                                    :disabled="unusedVarCount === 0"
 29 |                                    @click="handleClearUnused">
 30 |                             <Trash2 class="btn-icon" />
 31 |                             <span>清理未引用 ({{ unusedVarCount }})</span>
 32 |                         </el-button>
 33 |                     </div>
 34 | 
 35 |                     <!-- 用户变量列表 (完全向系统变量的简洁样式靠拢) -->
 36 |                     <div class="vars-list-scroll">
 37 |                         <template v-if="userVarList.length">
 38 |                             <div v-for="item in userVarList"
 39 |                                  :key="item.key"
 40 |                                  class="var-card-row">
 41 |                                 <!-- 左列：类型标识 Badge + 变量名 -->
 42 |                                 <div class="var-name-col">
 43 |                                     <span class="type-badge" :class="`type-${item.type}`">{{ item.typeLabel }}</span>
 44 |                                     <span class="var-name-text" :title="item.key">{{ item.key }}</span>
 45 |                                 </div>
 46 | 
 47 |                                 <!-- 中列：静态当前值预览 (无边框/无按键噪音) -->
 48 |                                 <div class="var-val-col">
 49 |                                     <span class="static-val-text" :title="item.displayValue">{{ item.displayValue }}</span>
 50 |                                 </div>
 51 | 
 52 |                                 <!-- 右列：默认显示引用次数，悬停淡入 Lucide 操作按钮组 -->
 53 |                                 <div class="var-action-col">
 54 |                                     <span class="ref-tag" :class="{ 'is-unused': item.refCount === 0 }">
 55 |                                         {{ item.refCount > 0 ? `${item.refCount} 次引用` : '—' }}
 56 |                                     </span>
 57 | 
 58 |                                     <div class="hover-action-group">
 59 |                                         <button type="button" class="icon-action-btn" title="复制表达式 {$var.xxx}" @click.stop="copyVarExpr(item.key)">
 60 |                                             <Copy class="lucide-svg" />
 61 |                                         </button>
 62 |                                         <button type="button" class="icon-action-btn" title="编辑变量" @click.stop="openEditDialog(item)">
 63 |                                             <Pencil class="lucide-svg" />
 64 |                                         </button>
 65 |                                         <button type="button" class="icon-action-btn danger" title="删除变量" @click.stop="handleDeleteVar(item.key)">
 66 |                                             <Trash2 class="lucide-svg" />
 67 |                                         </button>
 68 |                                     </div>
 69 |                                 </div>
 70 |                             </div>
 71 |                         </template>
 72 | 
 73 |                         <div v-else class="empty-vars-tip">
 74 |                             暂无自定义变量，请点击上方【新建变量】按钮创建
 75 |                         </div>
 76 |                     </div>
 77 |                 </div>
 78 |             </div>
 79 | 
 80 |             <!-- 2. 第二行：运行上下文变量 ($ctx) -->
 81 |             <div class="accordion-item" :class="{ 'is-expanded': expandedSection === 'ctx' }">
 82 |                 <div class="accordion-header" @click="toggleSection('ctx')">
 83 |                     <div class="header-left">
 84 |                         <span class="header-title">运行上下文变量 ($ctx)</span>
 85 |                     </div>
 86 |                     <ChevronDown class="arrow-icon" :class="{ 'is-rotated': expandedSection === 'ctx' }" />
 87 |                 </div>
 88 | 
 89 |                 <div v-show="expandedSection === 'ctx'" class="accordion-content">
 90 |                     <div class="vars-list-scroll">
 91 |                         <div class="ctx-form-box">
 92 |                             <template v-for="(config, field) in setWindowSchema" :key="field">
 93 |                                 <div v-if="!['on_success', 'on_failure'].includes(field)" class="ctx-param-item">
 94 |                                     <ParamRenderer :config="config"
 95 |                                                    :value="getCtxFieldValue(field)"
 96 |                                                    :label="config.label || field"
 97 |                                                    :context="ctxContextObject"
 98 |                                                    @update="val => handleCtxFieldUpdate(field, val)" />
 99 |                                 </div>
100 |                             </template>
101 |                         </div>
102 |                     </div>
103 |                 </div>
104 |             </div>
105 | 
106 |             <!-- 3. 第三行：系统环境变量 ($env) -->
107 |             <div class="accordion-item" :class="{ 'is-expanded': expandedSection === 'env' }">
108 |                 <div class="accordion-header" @click="toggleSection('env')">
109 |                     <div class="header-left">
110 |                         <span class="header-title">系统环境变量 ($env)</span>
111 |                     </div>
112 |                     <ChevronDown class="arrow-icon" :class="{ 'is-rotated': expandedSection === 'env' }" />
113 |                 </div>
114 | 
115 |                 <div v-show="expandedSection === 'env'" class="accordion-content">
116 |                     <div class="vars-list-scroll">
117 |                         <div v-for="env in systemEnvList"
118 |                              :key="env.key"
119 |                              class="var-card-row readonly-row">
120 |                             <div class="var-name-col">
121 |                                 <span class="var-name-text env-key">{{ env.key }}</span>
122 |                             </div>
123 |                             <div class="var-desc-col">
124 |                                 <span>{{ env.desc }}</span>
125 |                             </div>
126 |                             <div class="var-action-col">
127 |                                 <button type="button" class="icon-action-btn static-copy" title="复制变量名" @click.stop="copyVarName(env.key)">
128 |                                     <Copy class="lucide-svg" />
129 |                                 </button>
130 |                             </div>
131 |                         </div>
132 |                     </div>
133 |                 </div>
134 |             </div>
135 | 
136 |         </div>
137 | 
138 |         <!-- ⚡ 彻底复用 ParamRenderer 表单网关的新建/编辑变量弹窗 -->
139 |         <el-dialog v-model="varDialogVisible"
140 |                    :title="isEditing ? `✏️ 编辑变量 [${editingKey}]` : '➕ 新建全局变量'"
141 |                    width="460px"
142 |                    append-to-body
143 |                    destroy-on-close
144 |                    :close-on-click-modal="false">
145 |             <div class="dialog-form-body">
146 |                 <template v-for="(schema, field) in activeFormSchema" :key="field">
147 |                     <div class="form-item-wrapper">
148 |                         <ParamRenderer :config="schema"
149 |                                        :value="dialogFormPayload[field]"
150 |                                        :label="schema.label"
151 |                                        :context="dialogFormPayload"
152 |                                        @update="val => handleDialogParamUpdate(field, val)" />
153 |                     </div>
154 |                 </template>
155 |             </div>
156 | 
157 |             <template #footer>
158 |                 <div class="dialog-footer">
159 |                     <el-button class="pure-btn" @click="varDialogVisible = false">
160 |                         <X class="btn-icon" />
161 |                         <span>取消</span>
162 |                     </el-button>
163 |                     <el-button type="primary" class="pure-btn" @click="confirmSaveVar">
164 |                         <Check class="btn-icon" />
165 |                         <span>确认保存</span>
166 |                     </el-button>
167 |                 </div>
168 |             </template>
169 |         </el-dialog>
170 |     </div>
171 | </template>
172 | 
173 | <script setup>
174 |     import { ref, computed, reactive } from 'vue'
175 |     import { useMainStore } from '@/stores'
176 |     import { ElMessage, ElMessageBox } from 'element-plus'
177 |     import { Plus, Trash2, Copy, ChevronDown, Pencil, Check, X } from 'lucide-vue-next'
178 |     import ParamRenderer from '@/components/ParamRenderer.vue'
179 | 
180 |     const store = useMainStore()
181 |     const expandedSection = ref('user')
182 | 
183 |     const toggleSection = (key) => {
184 |         expandedSection.value = expandedSection.value === key ? null : key
185 |     }
186 | 
187 |     // 弹窗状态与表单模型
188 |     const varDialogVisible = ref(false)
189 |     const isEditing = ref(false)
190 |     const editingKey = ref('')
191 | 
192 |     const dialogFormPayload = reactive({
193 |         name: '',
194 |         type: 'string',
195 |         value_number: 0,
196 |         value_string: '',
197 |         value_bool: false,
198 |         value_json: ''
199 |     })
200 | 
201 |     // 打开新建变量弹窗
202 |     const openCreateDialog = () => {
203 |         isEditing.value = false
204 |         editingKey.value = ''
205 |         dialogFormPayload.name = ''
206 |         dialogFormPayload.type = 'number'
207 |         dialogFormPayload.value_number = 0
208 |         dialogFormPayload.value_string = ''
209 |         dialogFormPayload.value_bool = false
210 |         dialogFormPayload.value_json = '[]'
211 |         varDialogVisible.value = true
212 |     }
213 | 
214 |     // 打开编辑变量弹窗
215 |     const openEditDialog = (item) => {
216 |         isEditing.value = true
217 |         editingKey.value = item.key
218 |         dialogFormPayload.name = item.key
219 |         dialogFormPayload.type = item.type
220 | 
221 |         if (item.type === 'number') dialogFormPayload.value_number = Number(item.value) || 0
222 |         else if (item.type === 'string') dialogFormPayload.value_string = String(item.value ?? '')
223 |         else if (item.type === 'boolean') dialogFormPayload.value_bool = Boolean(item.value)
224 |         else dialogFormPayload.value_json = JSON.stringify(item.value ?? (item.type === 'list' ? [] : {}), null, 2)
225 | 
226 |         varDialogVisible.value = true
227 |     }
228 | 
229 |     // 动态注册交由 ParamRenderer 的编辑/新建 Schema
230 |     const activeFormSchema = computed(() => {
231 |         return {
232 |             name: {
233 |                 type: 'str',
234 |                 label: '变量名称',
235 |                 placeholder: '仅支持字母、数字、下划线，如 run_count'
236 |             },
237 |             type: {
238 |                 type: 'select',
239 |                 label: '数据类型',
240 |                 options: [
241 |                     { label: '数字 (Number)', value: 'number' },
242 |                     { label: '文本 (String)', value: 'string' },
243 |                     { label: '布尔 (Boolean)', value: 'boolean' },
244 |                     { label: '数组 (List)', value: 'list' },
245 |                     { label: '字典 (Dict)', value: 'dict' }
246 |                 ]
247 |             },
248 |             value_number: {
249 |                 type: 'int',
250 |                 label: '初始数值',
251 |                 default: 0,
252 |                 visible_if: { field: 'type', operator: 'eq', value: 'number' }
253 |             },
254 |             value_string: {
255 |                 type: 'str',
256 |                 label: '初始文本',
257 |                 default: '',
258 |                 placeholder: '请输入初始字符串',
259 |                 visible_if: { field: 'type', operator: 'eq', value: 'string' }
260 |             },
261 |             value_bool: {
262 |                 type: 'bool',
263 |                 label: '初始开关状态',
264 |                 default: false,
265 |                 visible_if: { field: 'type', operator: 'eq', value: 'boolean' }
266 |             },
267 |             value_json: {
268 |                 type: 'textarea',
269 |                 label: '初始 JSON 结构',
270 |                 default: '',
271 |                 placeholder: '列表如 ["a", "b"]；字典如 {"key": "val"}',
272 |                 rows: 3,
273 |                 visible_if: { field: 'type', operator: 'in', value: ['list', 'dict'] }
274 |             }
275 |         }
276 |     })
277 | 
278 |     const handleDialogParamUpdate = (field, val) => {
279 |         dialogFormPayload[field] = val
280 |     }
281 | 
282 |     // 确认保存（新建或编辑）
283 |     const confirmSaveVar = async () => {
284 |         const name = dialogFormPayload.name ? dialogFormPayload.name.trim() : ''
285 |         if (!name) return ElMessage.warning('请输入变量名称')
286 | 
287 |         if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name)) {
288 |             return ElMessage.warning('变量名称只能包含字母、数字和下划线，且不能以数字开头')
289 |         }
290 | 
291 |         if (!store.blueprint) store.blueprint = { variables: {} }
292 |         if (!store.blueprint.variables) store.blueprint.variables = {}
293 | 
294 |         if (isEditing.value && editingKey.value && editingKey.value !== name) {
295 |             delete store.blueprint.variables[editingKey.value]
296 |         } else if (!isEditing.value && store.blueprint.variables[name] !== undefined) {
297 |             return ElMessage.warning('该变量名称已存在，请勿重复创建')
298 |         }
299 | 
300 |         let parsedVal = ''
301 |         const type = dialogFormPayload.type
302 | 
303 |         if (type === 'number') parsedVal = Number(dialogFormPayload.value_number) || 0
304 |         else if (type === 'string') parsedVal = String(dialogFormPayload.value_string ?? '')
305 |         else if (type === 'boolean') parsedVal = Boolean(dialogFormPayload.value_bool)
306 |         else if (type === 'list' || type === 'dict') {
307 |             try {
308 |                 parsedVal = dialogFormPayload.value_json ? JSON.parse(dialogFormPayload.value_json) : (type === 'list' ? [] : {})
309 |             } catch {
310 |                 return ElMessage.error('JSON 格式解析失败，请检查语法')
311 |             }
312 |         }
313 | 
314 |         store.blueprint.variables[name] = parsedVal
315 |         await store.saveBlueprintImmediately()
316 |         ElMessage.success(`变量 [${name}] 保存成功`)
317 |         varDialogVisible.value = false
318 |     }
319 | 
320 |     // 上下文 Schema 与属性关联
321 |     const setWindowSchema = computed(() => store.paramsDefinitions?.set_window?.params || {})
322 | 
323 |     const ctxContextObject = computed(() => {
324 |         const ctx = store.currentContext || {}
325 |         return {
326 |             work_mode: ctx.workMode || 'window',
327 |             title: ctx.windowTitle || '',
328 |             is_emulator: !!ctx.isEmulator,
329 |             content_offset: getCtxFieldValue('content_offset'),
330 |             target_content_size: getCtxFieldValue('target_content_size')
331 |         }
332 |     })
333 | 
334 |     const getCtxFieldValue = (field) => {
335 |         const ctx = store.currentContext || {}
336 |         switch (field) {
337 |             case 'work_mode': return ctx.workMode || 'window'
338 |             case 'title': return ctx.windowTitle || ''
339 |             case 'is_emulator': return !!ctx.isEmulator
340 |             case 'content_offset':
341 |                 if (Array.isArray(ctx.contentOffset)) return ctx.contentOffset
342 |                 return [ctx.offsetTop || 0, ctx.offsetBottom || 0, ctx.offsetLeft || 0, ctx.offsetRight || 0]
343 |             case 'target_content_size':
344 |                 if (Array.isArray(ctx.targetSize)) return ctx.targetSize
345 |                 return [ctx.targetWidth || 0, ctx.targetHeight || 0]
346 |             default: return ''
347 |         }
348 |     }
349 | 
350 |     const handleCtxFieldUpdate = (field, val) => {
351 |         if (!store.currentContext) store.currentContext = {}
352 |         switch (field) {
353 |             case 'work_mode': store.currentContext.workMode = val; break
354 |             case 'title': store.currentContext.windowTitle = val; break
355 |             case 'is_emulator': store.currentContext.isEmulator = val; break
356 |             case 'content_offset':
357 |                 store.currentContext.contentOffset = val
358 |                 if (Array.isArray(val) && val.length >= 4) {
359 |                     store.currentContext.offsetTop = val[0] || 0
360 |                     store.currentContext.offsetBottom = val[1] || 0
361 |                     store.currentContext.offsetLeft = val[2] || 0
362 |                     store.currentContext.offsetRight = val[3] || 0
363 |                 }
364 |                 break
365 |             case 'target_content_size':
366 |                 store.currentContext.targetSize = val
367 |                 if (Array.isArray(val) && val.length >= 2) {
368 |                     store.currentContext.targetWidth = val[0] || 0
369 |                     store.currentContext.targetHeight = val[1] || 0
370 |                 }
371 |                 break
372 |         }
373 |         store.saveBlueprintImmediately()
374 |     }
375 | 
376 |     const systemEnvList = [
377 |         { key: '$env.current_time', desc: '系统当前时间戳 (ms)' },
378 |         { key: '$env.project_path', desc: '当前自动化项目根目录路径' },
379 |         { key: '$env.last_error', desc: '最近一次节点的运行报错信息' },
380 |         { key: '$env.loop_index', desc: '当前循环体内的索引序号' }
381 |     ]
382 | 
383 |     const varReferenceCounts = computed(() => {
384 |         const counts = {}
385 |         const tasks = store.blueprint?.tasks || []
386 | 
387 |         const scanObj = (obj) => {
388 |             if (!obj) return
389 |             if (typeof obj === 'string') {
390 |                 for (const varName of Object.keys(store.blueprint?.variables || {})) {
391 |                     if (obj === varName || obj.includes(`{${varName}}`) || obj.includes(`{$var.${varName}}`)) {
392 |                         counts[varName] = (counts[varName] || 0) + 1
393 |                     }
394 |                 }
395 |             } else if (typeof obj === 'object') {
396 |                 for (const val of Object.values(obj)) {
397 |                     scanObj(val)
398 |                 }
399 |             }
400 |         }
401 | 
402 |         tasks.forEach(t => {
403 |             (t.nodes || []).forEach(n => {
404 |                 scanObj(n.params)
405 |             })
406 |         })
407 | 
408 |         return counts
409 |     })
410 | 
411 |     const getVarType = (val) => {
412 |         if (typeof val === 'boolean') return { type: 'boolean', label: 'BOOL' }
413 |         if (typeof val === 'number') return { type: 'number', label: 'NUM' }
414 |         if (Array.isArray(val)) return { type: 'list', label: 'LIST' }
415 |         if (typeof val === 'object' && val !== null) return { type: 'dict', label: 'DICT' }
416 |         return { type: 'string', label: 'STR' }
417 |     }
418 | 
419 |     const formatDisplayValue = (val) => {
420 |         if (Array.isArray(val)) return `${val.length} 项 (List)`
421 |         if (typeof val === 'object' && val !== null) return `${Object.keys(val).length} 项 (Dict)`
422 |         if (typeof val === 'boolean') return val ? 'True' : 'False'
423 |         if (val === '' || val === undefined) return '—'
424 |         return String(val)
425 |     }
426 | 
427 |     const userVarList = computed(() => {
428 |         const varsObj = store.blueprint?.variables || {}
429 |         const refs = varReferenceCounts.value
430 | 
431 |         return Object.keys(varsObj).map(key => {
432 |             const val = varsObj[key]
433 |             const typeInfo = getVarType(val)
434 |             return {
435 |                 key,
436 |                 value: val,
437 |                 type: typeInfo.type,
438 |                 typeLabel: typeInfo.label,
439 |                 displayValue: formatDisplayValue(val),
440 |                 refCount: refs[key] || 0
441 |             }
442 |         })
443 |     })
444 | 
445 |     const unusedVarCount = computed(() => {
446 |         return userVarList.value.filter(v => v.refCount === 0).length
447 |     })
448 | 
449 |     const copyVarName = async (text) => {
450 |         try {
451 |             await navigator.clipboard.writeText(text)
452 |             ElMessage.success(`已复制变量名: ${text}`)
453 |         } catch {
454 |             ElMessage.error('复制失败')
455 |         }
456 |     }
457 | 
458 |     const copyVarExpr = async (varName) => {
459 |         const expr = `{$var.${varName}}`
460 |         try {
461 |             await navigator.clipboard.writeText(expr)
462 |             ElMessage.success(`已复制变量表达式: ${expr}`)
463 |         } catch {
464 |             ElMessage.error('复制失败')
465 |         }
466 |     }
467 | 
468 |     const handleDeleteVar = async (varName) => {
469 |         try {
470 |             await ElMessageBox.confirm(
471 |                 `确定要删除变量 [${varName}] 吗？删除后画布中对其引用的求值将失效。`,
472 |                 '删除变量确认',
473 |                 { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
474 |             )
475 |             delete store.blueprint.variables[varName]
476 |             await store.saveBlueprintImmediately()
477 |             ElMessage.success(`已删除变量 [${varName}]`)
478 |         } catch {
479 |             /* 取消删除 */
480 |         }
481 |     }
482 | 
483 |     const handleClearUnused = async () => {
484 |         const unusedList = userVarList.value.filter(v => v.refCount === 0).map(v => v.key)
485 |         if (unusedList.length === 0) return
486 | 
487 |         try {
488 |             await ElMessageBox.confirm(
489 |                 `确定要清理以下 ${unusedList.length} 个未引用的变量吗？\n${unusedList.join(', ')}`,
490 |                 '清理确认',
491 |                 { confirmButtonText: '确定清理', cancelButtonText: '取消', type: 'warning' }
492 |             )
493 | 
494 |             unusedList.forEach(key => {
495 |                 delete store.blueprint.variables[key]
496 |             })
497 |             await store.saveBlueprintImmediately()
498 |             ElMessage.success(`成功清理 ${unusedList.length} 个未引用变量`)
499 |         } catch (err) {
500 |             if (err !== 'cancel') ElMessage.error('清理失败')
501 |         }
502 |     }
503 | </script>
504 | 
505 | <style scoped>
506 |     .global-vars-panel {
507 |         width: 100%;
508 |         height: 100%;
509 |         display: flex;
510 |         flex-direction: column;
511 |         background: var(--el-bg-color);
512 |         box-sizing: border-box;
513 |         overflow-y: auto;
514 |     }
515 | 
516 |     .accordion-container {
517 |         display: flex;
518 |         flex-direction: column;
519 |         gap: 1px;
520 |         background: var(--el-border-color-light);
521 |     }
522 | 
523 |     .accordion-item {
524 |         background: var(--el-bg-color);
525 |         display: flex;
526 |         flex-direction: column;
527 |     }
528 | 
529 |     .accordion-header {
530 |         padding: 10px 12px;
531 |         background: rgba(25, 26, 38, 0.95);
532 |         cursor: pointer;
533 |         display: flex;
534 |         align-items: center;
535 |         justify-content: space-between;
536 |         user-select: none;
537 |         transition: background 0.2s;
538 |     }
539 | 
540 |         .accordion-header:hover {
541 |             background: rgba(38, 40, 61, 0.8);
542 |         }
543 | 
544 |     .header-left {
545 |         display: flex;
546 |         align-items: center;
547 |         gap: 8px;
548 |     }
549 | 
550 |     .header-title {
551 |         font-size: 12px;
552 |         font-weight: 600;
553 |         color: var(--el-text-color-primary);
554 |     }
555 | 
556 |     .tab-badge {
557 |         font-size: 10px;
558 |         background: rgba(78, 209, 156, 0.15);
559 |         color: var(--el-color-primary);
560 |         padding: 1px 5px;
561 |         border-radius: 10px;
562 |     }
563 | 
564 |     .arrow-icon {
565 |         width: 14px;
566 |         height: 14px;
567 |         color: var(--el-text-color-secondary);
568 |         transition: transform 0.2s ease;
569 |     }
570 | 
571 |         .arrow-icon.is-rotated {
572 |             transform: rotate(180deg);
573 |             color: var(--el-color-primary);
574 |         }
575 | 
576 |     .accordion-content {
577 |         display: flex;
578 |         flex-direction: column;
579 |         border-top: 1px solid var(--el-border-color-light);
580 |         background: var(--el-bg-color);
581 |     }
582 | 
583 |     .vars-toolbar {
584 |         padding: 8px 12px;
585 |         display: flex;
586 |         gap: 8px;
587 |         border-bottom: 1px solid var(--el-border-color-light);
588 |         flex-shrink: 0;
589 |     }
590 | 
591 |     .pure-btn {
592 |         display: flex;
593 |         align-items: center;
594 |         gap: 4px;
595 |     }
596 | 
597 |     .btn-icon {
598 |         width: 13px;
599 |         height: 13px;
600 |     }
601 | 
602 |     .vars-list-scroll {
603 |         padding: 10px 12px;
604 |         display: flex;
605 |         flex-direction: column;
606 |         gap: 8px;
607 |         max-height: 480px;
608 |         overflow-y: auto;
609 |     }
610 | 
611 |     /* ⚡ 卡片网格对齐样式 */
612 |     .var-card-row {
613 |         position: relative;
614 |         background: var(--el-fill-color-blank);
615 |         border: 1px solid var(--el-border-color-light);
616 |         border-radius: 6px;
617 |         padding: 8px 10px;
618 |         display: flex;
619 |         align-items: center;
620 |         justify-content: space-between;
621 |         gap: 8px;
622 |         transition: border-color 0.2s, background-color 0.2s;
623 |     }
624 | 
625 |         .var-card-row:hover {
626 |             border-color: var(--el-color-primary);
627 |             background-color: rgba(78, 209, 156, 0.03);
628 |         }
629 | 
630 |     .var-name-col {
631 |         display: flex;
632 |         align-items: center;
633 |         gap: 6px;
634 |         width: 130px;
635 |         flex-shrink: 0;
636 |     }
637 | 
638 |     .type-badge {
639 |         font-size: 9px;
640 |         font-weight: bold;
641 |         padding: 1px 4px;
642 |         border-radius: 3px;
643 |         color: #fff;
644 |         line-height: 1.2;
645 |         flex-shrink: 0;
646 |     }
647 | 
648 |     .type-number {
649 |         background: #409eff;
650 |     }
651 | 
652 |     .type-string {
653 |         background: #67c23a;
654 |     }
655 | 
656 |     .type-boolean {
657 |         background: #e6a23c;
658 |     }
659 | 
660 |     .type-list {
661 |         background: #909399;
662 |     }
663 | 
664 |     .type-dict {
665 |         background: #f56c6c;
666 |     }
667 | 
668 |     .var-name-text {
669 |         font-size: 12px;
670 |         font-weight: 600;
671 |         color: var(--el-text-color-primary);
672 |         white-space: nowrap;
673 |         overflow: hidden;
674 |         text-overflow: ellipsis;
675 |     }
676 | 
677 |     .env-key {
678 |         color: var(--el-color-primary);
679 |     }
680 | 
681 |     .var-val-col {
682 |         flex: 1;
683 |         text-align: center;
684 |         padding: 0 8px;
685 |         overflow: hidden;
686 |     }
687 | 
688 |     .static-val-text {
689 |         font-size: 12px;
690 |         color: var(--el-text-color-regular);
691 |         white-space: nowrap;
692 |         overflow: hidden;
693 |         text-overflow: ellipsis;
694 |         display: block;
695 |     }
696 | 
697 |     .var-action-col {
698 |         display: flex;
699 |         align-items: center;
700 |         justify-content: flex-end;
701 |         width: 90px;
702 |         flex-shrink: 0;
703 |     }
704 | 
705 |     .ref-tag {
706 |         font-size: 10px;
707 |         color: var(--el-color-primary);
708 |         background: rgba(78, 209, 156, 0.1);
709 |         padding: 2px 6px;
710 |         border-radius: 4px;
711 |         white-space: nowrap;
712 |     }
713 | 
714 |         .ref-tag.is-unused {
715 |             color: var(--el-text-color-placeholder);
716 |             background: transparent;
717 |         }
718 | 
719 |     /* ⚡ 鼠标悬停时平滑替换为 Lucide 图标集 */
720 |     .hover-action-group {
721 |         display: none;
722 |         align-items: center;
723 |         gap: 4px;
724 |     }
725 | 
726 |     .var-card-row:hover .ref-tag {
727 |         display: none;
728 |     }
729 | 
730 |     .var-card-row:hover .hover-action-group {
731 |         display: flex;
732 |     }
733 | 
734 |     .icon-action-btn {
735 |         background: transparent;
736 |         border: none;
737 |         color: var(--el-text-color-secondary);
738 |         cursor: pointer;
739 |         padding: 3px;
740 |         border-radius: 4px;
741 |         display: flex;
742 |         align-items: center;
743 |         justify-content: center;
744 |         transition: all 0.2s;
745 |     }
746 | 
747 |         .icon-action-btn:hover {
748 |             color: var(--el-color-primary);
749 |             background: rgba(255, 255, 255, 0.08);
750 |         }
751 | 
752 |         .icon-action-btn.danger:hover {
753 |             color: var(--el-color-danger);
754 |             background: rgba(245, 108, 108, 0.15);
755 |         }
756 | 
757 |         .icon-action-btn.static-copy {
758 |             opacity: 0;
759 |         }
760 | 
761 |     .var-card-row:hover .icon-action-btn.static-copy {
762 |         opacity: 1;
763 |     }
764 | 
765 |     .lucide-svg {
766 |         width: 13px;
767 |         height: 13px;
768 |     }
769 | 
770 |     .readonly-row {
771 |         opacity: 0.9;
772 |     }
773 | 
774 |     .var-desc-col {
775 |         flex: 1;
776 |         font-size: 11px;
777 |         color: var(--el-text-color-secondary);
778 |         text-align: right;
779 |         padding-right: 6px;
780 |     }
781 | 
782 |     .empty-vars-tip {
783 |         font-size: 11px;
784 |         color: var(--el-text-color-placeholder);
785 |         text-align: center;
786 |         padding: 20px 0;
787 |         line-height: 1.6;
788 |     }
789 | 
790 |     .ctx-form-box {
791 |         padding: 4px 0;
792 |         display: flex;
793 |         flex-direction: column;
794 |         gap: 8px;
795 |     }
796 | 
797 |     .ctx-param-item {
798 |         width: 100%;
799 |     }
800 | 
801 |     .dialog-form-body {
802 |         display: flex;
803 |         flex-direction: column;
804 |         gap: 12px;
805 |     }
806 | 
807 |     .form-item-wrapper {
808 |         width: 100%;
809 |     }
810 | 
811 |     .dialog-footer {
812 |         display: flex;
813 |         justify-content: flex-end;
814 |         gap: 10px;
815 |     }
816 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\panels\LogPanel.vue

- Extension: .vue
- Language: unknown
- Size: 5889 bytes
- Created: 2026-08-01 21:53:50
- Modified: 2026-08-08 22:53:36

### Code

```unknown
  1 | ﻿<!-- frontend/src/components/panels/LogPanel.vue -->
  2 | <template>
  3 |     <div class="log-panel">
  4 |         <div class="log-toolbar">
  5 |             <span class="log-count">共 {{ logs.length }} 条日志 ({{ runStatus }})</span>
  6 |             <el-button type="info" link size="small" @click="clearLogs">🗑️ 清空日志</el-button>
  7 |         </div>
  8 |         <div class="log-container" ref="logContainerRef">
  9 |             <div v-for="(item, idx) in logs"
 10 |                  :key="idx"
 11 |                  class="log-line"
 12 |                  :class="getLogLevelClass(item)">
 13 |                 <span class="log-time">[{{ item.time || 'INFO' }}]</span>
 14 |                 <span class="log-text">{{ item.message }}</span>
 15 | 
 16 |                 <!-- 调试截图悬浮预览 -->
 17 |                 <template v-if="item.image">
 18 |                     <el-popover placement="left" :width="350" trigger="hover" append-to-body>
 19 |                         <template #reference>
 20 |                             <el-tag size="small" type="success" class="img-badge">🖼️ 查看调试截图</el-tag>
 21 |                         </template>
 22 |                         <div class="img-preview-card">
 23 |                             <div class="preview-title">🎯 实际框选识别区域图像</div>
 24 |                             <img :src="item.image" style="width: 100%; border-radius: 4px; border: 1px solid #67C23A;" />
 25 |                         </div>
 26 |                     </el-popover>
 27 |                 </template>
 28 |             </div>
 29 |             <div v-if="!logs.length" class="empty-log">
 30 |                 ⚡ 暂无执行日志，点击“运行”后将在此处实时显示...
 31 |             </div>
 32 |         </div>
 33 |     </div>
 34 | </template>
 35 | 
 36 | <script setup>
 37 |     import { ref, watch, nextTick, onUnmounted } from 'vue'
 38 |     import { useMainStore } from '@/stores'
 39 | 
 40 |     const store = useMainStore()
 41 |     const logContainerRef = ref(null)
 42 |     const logs = ref([])
 43 |     const runStatus = ref('就绪')
 44 | 
 45 |     let eventSource = null
 46 | 
 47 |     // 监听 store 中当前活跃的 executionId 并自动开启 SSE 订阅
 48 |     watch(() => store.currentExecutionId, (execId) => {
 49 |         if (eventSource) {
 50 |             eventSource.close()
 51 |             eventSource = null
 52 |         }
 53 | 
 54 |         if (!execId) return
 55 | 
 56 |         logs.value = []
 57 |         eventSource = new EventSource(`/api/execution/${execId}/stream`)
 58 | 
 59 |         eventSource.onmessage = (event) => {
 60 |             try {
 61 |                 const data = JSON.parse(event.data)
 62 |                 if (data.status) {
 63 |                     runStatus.value = data.status.message || data.status.status
 64 |                 }
 65 |                 if (data.logs && data.logs.length > 0) {
 66 |                     logs.value.push(...data.logs)
 67 |                 }
 68 |                 if (data.status && ['success', 'error'].includes(data.status.status)) {
 69 |                     eventSource.close()
 70 |                     eventSource = null
 71 |                 }
 72 |             } catch (e) {
 73 |                 console.error('解析 SSE 数据异常', e)
 74 |             }
 75 |         }
 76 | 
 77 |         eventSource.onerror = () => {
 78 |             if (eventSource) {
 79 |                 eventSource.close()
 80 |                 eventSource = null
 81 |             }
 82 |         }
 83 |     }, { immediate: true })
 84 | 
 85 |     watch(() => logs.value.length, () => {
 86 |         nextTick(() => {
 87 |             if (logContainerRef.value) {
 88 |                 logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
 89 |             }
 90 |         })
 91 |     })
 92 | 
 93 |     const getLogLevelClass = (item) => {
 94 |         const msg = item.message || ''
 95 |         if (msg.includes('💥') || msg.includes('❌') || msg.includes('ERROR')) return 'log-error'
 96 |         if (msg.includes('⚠️') || msg.includes('WARNING')) return 'log-warn'
 97 |         if (msg.includes('🎯') || msg.includes('✅')) return 'log-success'
 98 |         return 'log-info'
 99 |     }
100 | 
101 |     const clearLogs = () => {
102 |         logs.value = []
103 |     }
104 | 
105 |     onUnmounted(() => {
106 |         if (eventSource) {
107 |             eventSource.close()
108 |         }
109 |     })
110 | </script>
111 | 
112 | <style scoped>
113 |     .log-panel {
114 |         display: flex;
115 |         flex-direction: column;
116 |         height: 100%;
117 |         background: var(--el-bg-color-page);
118 |         font-family: 'Consolas', 'Courier New', monospace;
119 |     }
120 | 
121 |     .log-toolbar {
122 |         display: flex;
123 |         justify-content: space-between;
124 |         align-items: center;
125 |         padding: 4px 12px;
126 |         background: var(--el-bg-color);
127 |         border-bottom: 1px solid var(--el-border-color-light);
128 |         font-size: 11px;
129 |     }
130 | 
131 |     .log-count {
132 |         color: var(--el-text-color-secondary);
133 |     }
134 | 
135 |     .log-container {
136 |         flex: 1;
137 |         padding: 8px 12px;
138 |         overflow-y: auto;
139 |         display: flex;
140 |         flex-direction: column;
141 |         gap: 6px;
142 |     }
143 | 
144 |     .log-line {
145 |         font-size: 12px;
146 |         line-height: 1.5;
147 |         white-space: pre-wrap;
148 |         word-break: break-all;
149 |         display: flex;
150 |         align-items: center;
151 |         gap: 8px;
152 |     }
153 | 
154 |     .log-time {
155 |         color: var(--el-text-color-secondary);
156 |         font-size: 11px;
157 |         flex-shrink: 0;
158 |     }
159 | 
160 |     .log-text {
161 |         flex: 1;
162 |     }
163 | 
164 |     .log-info {
165 |         color: var(--el-text-color-regular);
166 |     }
167 | 
168 |     .log-success {
169 |         color: var(--el-color-primary);
170 |     }
171 | 
172 |     .log-warn {
173 |         color: #e6a23c;
174 |     }
175 | 
176 |     .log-error {
177 |         color: #f56c6c;
178 |         font-weight: bold;
179 |     }
180 | 
181 |     .img-badge {
182 |         cursor: pointer;
183 |         margin-left: 6px;
184 |     }
185 | 
186 |     .preview-title {
187 |         font-size: 12px;
188 |         font-weight: bold;
189 |         color: var(--el-color-primary);
190 |         margin-bottom: 6px;
191 |     }
192 | 
193 |     .empty-log {
194 |         color: var(--el-text-color-placeholder);
195 |         font-size: 12px;
196 |         text-align: center;
197 |         margin-top: 20px;
198 |     }
199 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\panels\NodeEditorPanel.vue

- Extension: .vue
- Language: unknown
- Size: 24692 bytes
- Created: 2026-07-28 20:52:23
- Modified: 2026-08-03 17:33:21

### Code

```unknown
  1 | <template>
  2 |     <div class="node-editor-panel">
  3 |         <div v-if="store.selectedNode" class="editor-form">
  4 |             <div class="node-title">
  5 |                 <span class="node-type-badge">{{ nodeTypeLabel }}</span>
  6 |                 <span class="node-name">{{ store.selectedNode.node_name }}</span>
  7 |             </div>
  8 | 
  9 |             <el-divider content-position="left">参数配置与调优区</el-divider>
 10 |             <div class="params-container">
 11 |                 <!-- 1. 通用字段渲染 -->
 12 |                 <template v-for="(config, paramName) in allParams" :key="paramName">
 13 |                     <!-- 区域坐标显隐 -->
 14 |                     <div v-if="paramName === 'region_value'"
 15 |                          v-show="shouldShowRegionValue"
 16 |                          class="param-item">
 17 |                         <ParamRenderer :key="paramName + store.selectedNodeId"
 18 |                                        :config="config"
 19 |                                        :value="store.selectedNode.params.region_value"
 20 |                                        :label="config.label || paramName"
 21 |                                        :context="store.selectedNode.params"
 22 |                                        @update="(val) => handleParamUpdate(paramName, val)" />
 23 |                     </div>
 24 | 
 25 |                     <!-- 灰度滑块（处于开启状态时） -->
 26 |                     <div v-else-if="paramName === 'gray_threshold' && store.selectedNode.params.gray_scale"
 27 |                          class="param-item slider-box">
 28 |                         <div class="slider-header">
 29 |                             <span>二值化灰度阈值: <strong>{{ store.selectedNode.params.gray_threshold ?? 127 }}</strong></span>
 30 |                             <span class="slider-tip">(向左增强浅色，向右过滤背景)</span>
 31 |                         </div>
 32 |                         <el-slider v-model="store.selectedNode.params.gray_threshold"
 33 |                                    :min="0"
 34 |                                    :max="255"
 35 |                                    :step="1"
 36 |                                    @input="debounceRefreshRealtime" />
 37 |                     </div>
 38 | 
 39 |                     <!-- 其他通用组件（排除跳转和候选列表，由下方独立接管） -->
 40 |                     <div v-else-if="!['region_value', 'gray_threshold', 'on_success', 'on_failure', 'candidates'].includes(paramName)"
 41 |                          class="param-item">
 42 |                         <ParamRenderer :key="paramName + store.selectedNodeId"
 43 |                                        :config="config"
 44 |                                        :value="store.selectedNode.params[paramName]"
 45 |                                        :label="config.label || paramName"
 46 |                                        :context="store.selectedNode.params"
 47 |                                        @update="(val) => handleParamUpdate(paramName, val)" />
 48 |                     </div>
 49 |                 </template>
 50 | 
 51 |                 <!-- ⭐⭐⭐ 2. 特别针对 branch 节点的 candidates 候选条件列表独立渲染 -->
 52 |                 <div v-if="store.selectedNode.node_type === 'branch' && allParams.candidates" class="param-item">
 53 |                     <ParamRenderer :key="'candidates_' + store.selectedNodeId"
 54 |                                    :config="allParams.candidates"
 55 |                                    :value="store.selectedNode.params.candidates"
 56 |                                    :label="allParams.candidates.label || '多分支判定列表'"
 57 |                                    :context="store.selectedNode.params"
 58 |                                    @update="(val) => handleParamUpdate('candidates', val)" />
 59 |                 </div>
 60 | 
 61 |                 <!-- ⭐⭐⭐ 3. 文字识别 (OCR) 实时调优卡片 -->
 62 |                 <div v-if="store.selectedNode.node_type === 'ocr_recognition'" class="interactive-preview-card">
 63 |                     <div class="preview-header">
 64 |                         <span>👁️ OCR 实时视场与文本预览</span>
 65 |                         <el-button size="small" type="primary" link :loading="previewLoading" @click="fetchPreview">
 66 |                             🔄 刷新视角
 67 |                         </el-button>
 68 |                     </div>
 69 |                     <div class="preview-body">
 70 |                         <div class="preview-box">
 71 |                             <div class="box-tag">二值化视角图</div>
 72 |                             <img v-if="previewImg" :src="previewImg" class="realtime-img" />
 73 |                             <div v-else class="placeholder">未框选有效区域</div>
 74 |                         </div>
 75 |                         <div class="preview-box">
 76 |                             <div class="box-tag">抓取文本结果</div>
 77 |                             <div class="realtime-text" :class="{ empty: !previewText }">
 78 |                                 {{ previewText || '(未识别到文本)' }}
 79 |                             </div>
 80 |                         </div>
 81 |                     </div>
 82 |                 </div>
 83 | 
 84 |                 <!-- ⭐⭐⭐ 4. 图像识别 实时调优卡片 -->
 85 |                 <div v-if="store.selectedNode.node_type === 'image_recognition'" class="interactive-preview-card">
 86 |                     <div class="preview-header">
 87 |                         <span>🎯 图像匹配实时对比分析</span>
 88 |                         <el-button size="small" type="primary" link :loading="previewLoading" @click="fetchPreview">
 89 |                             🔄 刷新视角
 90 |                         </el-button>
 91 |                     </div>
 92 |                     <div class="preview-body">
 93 |                         <div class="preview-box">
 94 |                             <div class="box-tag">二值化搜索画幅 (红框为找到的目标)</div>
 95 |                             <img v-if="previewImg" :src="previewImg" class="realtime-img" />
 96 |                             <div v-else class="placeholder">请先选择模板图片</div>
 97 |                         </div>
 98 |                         <div class="preview-box stat-box">
 99 |                             <div class="box-tag">匹配得分与位置</div>
100 |                             <div class="stat-score" :class="{ pass: isMatchPass }">
101 |                                 {{ imageScore }}%
102 |                             </div>
103 |                             <div class="stat-detail">
104 |                                 <span>判定: <strong>{{ isMatchPass ? '✅ 匹配成功' : '❌ 未达阈值' }}</strong></span>
105 |                                 <span>中心点: <strong>{{ imageCenterPos }}</strong></span>
106 |                             </div>
107 |                         </div>
108 |                     </div>
109 |                 </div>
110 | 
111 |                 <!-- ⭐⭐⭐ 5. 恢复所有判断/行为节点的【成功跳转】与【失败跳转】配置区 -->
112 |                 <template v-if="hasJumpConfig">
113 |                     <div v-for="jumpKey in jumpKeysList" :key="jumpKey" class="jump-section">
114 |                         <el-divider content-position="left">
115 |                             {{ jumpKey === 'on_success' ? '成功跳转' : (store.selectedNode.node_type === 'branch' ? '兜底失败跳转 (全不满足时)' : '失败跳转') }}
116 |                         </el-divider>
117 |                         <div class="jump-config">
118 |                             <div class="param-item">
119 |                                 <ParamRenderer :config="jumpTypeConfig"
120 |                                                :value="store.selectedNode.params[jumpKey]?.jump_type || store.selectedNode.params[jumpKey]?.type || 'next'"
121 |                                                label="跳转类型"
122 |                                                :context="store.selectedNode.params"
123 |                                                @update="(val) => updateJumpParam(jumpKey, 'jump_type', val)" />
124 |                             </div>
125 |                             <!-- 动态目标任务 -->
126 |                             <div v-if="['task'].includes(store.selectedNode.params[jumpKey]?.jump_type || store.selectedNode.params[jumpKey]?.type)" class="param-item">
127 |                                 <ParamRenderer :config="getTargetConfig(jumpKey)"
128 |                                                :value="store.selectedNode.params[jumpKey]?.target_task || store.selectedNode.params[jumpKey]?.target || ''"
129 |                                                label="目标任务"
130 |                                                :context="store.selectedNode.params"
131 |                                                @update="(val) => updateJumpParam(jumpKey, 'target_task', val)" />
132 |                             </div>
133 |                             <!-- 动态目标节点 -->
134 |                             <div v-if="['node', 'task'].includes(store.selectedNode.params[jumpKey]?.jump_type || store.selectedNode.params[jumpKey]?.type)" class="param-item">
135 |                                 <ParamRenderer :config="getTargetNodeConfig(jumpKey)"
136 |                                                :value="store.selectedNode.params[jumpKey]?.target_node || ''"
137 |                                                label="目标节点"
138 |                                                :context="store.selectedNode.params"
139 |                                                @update="(val) => updateJumpParam(jumpKey, 'target_node', val)" />
140 |                             </div>
141 |                         </div>
142 |                     </div>
143 |                 </template>
144 |             </div>
145 | 
146 |             <div class="save-actions">
147 |                 <el-button type="primary" size="small" @click="saveNode">保存参数</el-button>
148 |             </div>
149 |         </div>
150 |         <div v-else class="empty">请从节点列表中选择一个节点</div>
151 |     </div>
152 | </template>
153 | 
154 | <script>
155 |     import { useMainStore } from '@/stores'
156 |     import { computed, ref, watch } from 'vue'
157 |     import ParamRenderer from '@/components/ParamRenderer.vue'
158 |     import { ElMessage } from 'element-plus'
159 |     import { logger } from '@/utils/logger'
160 |     import axios from 'axios'
161 | 
162 |     export default {
163 |         name: 'NodeEditorPanel',
164 |         components: { ParamRenderer },
165 |         setup() {
166 |             const store = useMainStore()
167 | 
168 |             const previewLoading = ref(false)
169 |             const previewText = ref('')
170 |             const previewImg = ref('')
171 |             const imageScore = ref(0)
172 |             const imageCenterPos = ref('(0, 0)')
173 |             const originalRecordedRegion = ref(null)
174 |             let isSyncingRecorded = false
175 |             let timer = null
176 | 
177 |             const paramDefs = computed(() => {
178 |                 const node = store.selectedNode
179 |                 if (!node) return {}
180 |                 return store.params[node.node_type]?.params || {}
181 |             })
182 | 
183 |             const nodeTypeLabel = computed(() => {
184 |                 const node = store.selectedNode
185 |                 if (!node) return ''
186 |                 return store.params[node.node_type]?.label || node.node_type
187 |             })
188 | 
189 |             // 判断当前节点是否包含跳转配置
190 |             const hasJumpConfig = computed(() => {
191 |                 const defs = paramDefs.value
192 |                 return defs && ('on_success' in defs || 'on_failure' in defs)
193 |             })
194 | 
195 |             // 动态决定要渲染哪些跳转区
196 |             const jumpKeysList = computed(() => {
197 |                 const defs = paramDefs.value
198 |                 const keys = []
199 |                 if ('on_success' in defs) keys.push('on_success')
200 |                 if ('on_failure' in defs) keys.push('on_failure')
201 |                 return keys
202 |             })
203 | 
204 |             const shouldShowRegionValue = computed(() => {
205 |                 const node = store.selectedNode
206 |                 if (!node || !node.params) return false
207 |                 const nodeType = node.node_type
208 |                 if (nodeType === 'ocr_recognition') return true
209 |                 const regionType = node.params.region_type
210 |                 return regionType === 'recorded' || regionType === 'custom'
211 |             })
212 | 
213 |             const isMatchPass = computed(() => {
214 |                 const targetThreshold = store.selectedNode?.params?.threshold ?? 85
215 |                 return imageScore.value >= targetThreshold
216 |             })
217 | 
218 |             const allParams = computed(() => paramDefs.value)
219 | 
220 |             const jumpTypeConfig = {
221 |                 type: 'select',
222 |                 options: [
223 |                     { value: 'next', label: '下一个节点' },
224 |                     { value: 'node', label: '跳转节点' },
225 |                     { value: 'task', label: '跳转任务' },
226 |                     { value: 'end', label: '结束流程' }
227 |                 ],
228 |                 default: 'next',
229 |                 label: '跳转类型'
230 |             }
231 | 
232 |             const getTargetConfig = (jumpKey) => ({
233 |                 type: 'select',
234 |                 options: (store.tasks || []).map(t => ({ value: t.task_id, label: t.task_name || t.task_id })),
235 |                 default: '',
236 |                 label: '目标任务'
237 |             })
238 | 
239 |             const getTargetNodeConfig = (jumpKey) => ({
240 |                 type: 'select',
241 |                 options: (store.nodes || []).map(n => ({ value: n.node_id, label: n.node_name || n.node_id })),
242 |                 default: '',
243 |                 label: '目标节点'
244 |             })
245 | 
246 |             const handleParamUpdate = (paramName, value) => {
247 |                 const node = store.selectedNode
248 |                 if (!node) return
249 | 
250 |                 if (paramName === 'region_value' && node.params.region_type === 'recorded' && !isSyncingRecorded) {
251 |                     if (originalRecordedRegion.value && JSON.stringify(value) !== JSON.stringify(originalRecordedRegion.value)) {
252 |                         node.params.region_type = 'custom'
253 |                         ElMessage.info('检测到坐标手动微调，已自动切换为【自定义区域】模式')
254 |                     }
255 |                 }
256 | 
257 |                 node.params[paramName] = value
258 |                 node.params = { ...node.params }
259 | 
260 |                 if (paramName === 'region_type' && value === 'recorded') {
261 |                     syncRecordedRegion()
262 |                 }
263 |                 if (paramName === 'image_source' && node.params.region_type === 'recorded') {
264 |                     syncRecordedRegion()
265 |                 }
266 | 
267 |                 if (['image_source', 'region_value', 'region_type', 'gray_scale', 'gray_threshold', 'threshold'].includes(paramName)) {
268 |                     debounceRefreshRealtime()
269 |                 }
270 |             }
271 | 
272 |             const updateJumpParam = (jumpKey, subKey, value) => {
273 |                 const node = store.selectedNode
274 |                 if (!node) return
275 |                 if (!node.params[jumpKey]) {
276 |                     node.params[jumpKey] = { jump_type: 'next', target_task: '', target_node: '' }
277 |                 }
278 |                 node.params[jumpKey][subKey] = value
279 |                 node.params = { ...node.params }
280 |             }
281 | 
282 |             const syncRecordedRegion = async () => {
283 |                 const node = store.selectedNode
284 |                 if (!node || !store.currentProjectPath) return
285 | 
286 |                 const rawTemplateName = node.params.image_source
287 |                 if (!rawTemplateName) return
288 | 
289 |                 isSyncingRecorded = true
290 |                 try {
291 |                     const res = await axios.get('/api/regions', {
292 |                         params: { project_path: store.currentProjectPath }
293 |                     })
294 |                     const regions = res.data || {}
295 |                     const cleanName = rawTemplateName.replace(/\.png$/i, '').replace(/\\/g, '/')
296 |                     const fileNameOnly = cleanName.split('/').pop()
297 | 
298 |                     const rect = regions[rawTemplateName] || regions[cleanName] || regions[fileNameOnly] || regions[`${cleanName}.png`] || regions[`${fileNameOnly}.png`]
299 | 
300 |                     if (rect && Array.isArray(rect) && rect.length === 4) {
301 |                         node.params.region_value = [...rect]
302 |                         originalRecordedRegion.value = [...rect]
303 |                         debounceRefreshRealtime()
304 |                     }
305 |                 } catch (err) {
306 |                     logger.error('NodeEditor', '获取区域配置失败:', err)
307 |                 } finally {
308 |                     setTimeout(() => { isSyncingRecorded = false }, 300)
309 |                 }
310 |             }
311 | 
312 |             const debounceRefreshRealtime = () => {
313 |                 if (timer) clearTimeout(timer)
314 |                 timer = setTimeout(() => {
315 |                     fetchPreview()
316 |                 }, 150)
317 |             }
318 | 
319 |             const fetchPreview = async () => {
320 |                 const node = store.selectedNode
321 |                 if (!node) return
322 | 
323 |                 previewLoading.value = true
324 |                 try {
325 |                     if (node.node_type === 'ocr_recognition') {
326 |                         const res = await axios.post('/api/ocr/test', {
327 |                             project_path: store.currentProjectPath,
328 |                             region_value: node.params.region_value || [0, 0, 0, 0],
329 |                             gray_scale: node.params.gray_scale ?? true,
330 |                             gray_threshold: node.params.gray_threshold ?? 127
331 |                         })
332 |                         previewText.value = res.data.text
333 |                         previewImg.value = res.data.image
334 |                     } else if (node.node_type === 'image_recognition') {
335 |                         if (!node.params.image_source) {
336 |                             previewImg.value = ''
337 |                             imageScore.value = 0
338 |                             return
339 |                         }
340 |                         const res = await axios.post('/api/image/test', {
341 |                             project_path: store.currentProjectPath,
342 |                             template_name: node.params.image_source,
343 |                             region_type: node.params.region_type || 'fullwindow',
344 |                             region_value: node.params.region_value || [0, 0, 0, 0],
345 |                             gray_scale: node.params.gray_scale ?? true,
346 |                             gray_threshold: node.params.gray_threshold ?? 127
347 |                         })
348 |                         imageScore.value = res.data.confidence
349 |                         imageCenterPos.value = JSON.stringify(res.data.center_pos)
350 |                         previewImg.value = res.data.image
351 |                     }
352 |                 } catch (err) {
353 |                     console.error('实时预览调用异常', err)
354 |                 } finally {
355 |                     previewLoading.value = false
356 |                 }
357 |             }
358 | 
359 |             watch(
360 |                 () => store.selectedNodeId,
361 |                 (newId) => {
362 |                     if (newId) {
363 |                         const node = store.selectedNode
364 |                         if (node?.params?.region_type === 'recorded') {
365 |                             syncRecordedRegion()
366 |                         }
367 |                         if (['ocr_recognition', 'image_recognition'].includes(node?.node_type)) {
368 |                             fetchPreview()
369 |                         }
370 |                     }
371 |                 },
372 |                 { immediate: true }
373 |             )
374 | 
375 |             const saveNode = async () => {
376 |                 try {
377 |                     await store.saveCurrentTask(true)
378 |                     ElMessage.success('参数已保存')
379 |                 } catch (err) {
380 |                     ElMessage.error('保存失败')
381 |                 }
382 |             }
383 | 
384 |             return {
385 |                 store,
386 |                 allParams,
387 |                 shouldShowRegionValue,
388 |                 hasJumpConfig,
389 |                 jumpKeysList,
390 |                 jumpTypeConfig,
391 |                 getTargetConfig,
392 |                 getTargetNodeConfig,
393 |                 nodeTypeLabel,
394 |                 previewLoading,
395 |                 previewText,
396 |                 previewImg,
397 |                 imageScore,
398 |                 imageCenterPos,
399 |                 isMatchPass,
400 |                 handleParamUpdate,
401 |                 updateJumpParam,
402 |                 debounceRefreshRealtime,
403 |                 fetchPreview,
404 |                 saveNode
405 |             }
406 |         }
407 |     }
408 | </script>
409 | 
410 | <style scoped>
411 |     .node-editor-panel {
412 |         height: 100%;
413 |         padding: 16px;
414 |         overflow-y: auto;
415 |         background-color: var(--el-bg-color);
416 |     }
417 | 
418 |     .node-title {
419 |         display: flex;
420 |         align-items: center;
421 |         gap: 10px;
422 |         margin-bottom: 16px;
423 |     }
424 | 
425 |     .node-type-badge {
426 |         background: var(--el-fill-color-blank);
427 |         color: var(--el-color-primary);
428 |         border: 1px solid var(--el-border-color-light);
429 |         padding: 2px 12px;
430 |         border-radius: 12px;
431 |         font-size: 12px;
432 |         font-weight: bold;
433 |     }
434 | 
435 |     .node-name {
436 |         color: var(--el-text-color-primary);
437 |         font-size: 18px;
438 |         font-weight: 600;
439 |     }
440 | 
441 |     .params-container {
442 |         display: flex;
443 |         flex-direction: column;
444 |         gap: 12px;
445 |     }
446 | 
447 |     .param-item {
448 |         display: flex;
449 |         flex-direction: column;
450 |         gap: 4px;
451 |     }
452 | 
453 |     .jump-section {
454 |         border-top: 1px solid var(--el-border-color-light);
455 |         padding-top: 12px;
456 |         margin-top: 8px;
457 |     }
458 | 
459 |     .jump-config {
460 |         display: flex;
461 |         flex-direction: column;
462 |         gap: 12px;
463 |         padding-left: 12px;
464 |     }
465 | 
466 |     .slider-box {
467 |         background: var(--el-fill-color-blank);
468 |         padding: 10px 12px;
469 |         border-radius: 8px;
470 |         border: 1px solid var(--el-border-color-light);
471 |     }
472 | 
473 |     .slider-header {
474 |         display: flex;
475 |         justify-content: space-between;
476 |         font-size: 12px;
477 |         color: var(--el-text-color-primary);
478 |         margin-bottom: 4px;
479 |     }
480 | 
481 |     .slider-tip {
482 |         color: var(--el-text-color-secondary);
483 |         font-size: 11px;
484 |     }
485 | 
486 |     .interactive-preview-card {
487 |         background: var(--el-fill-color-blank);
488 |         border: 1px solid var(--el-border-color-light);
489 |         border-radius: 8px;
490 |         padding: 12px;
491 |         margin-top: 4px;
492 |     }
493 | 
494 |     .preview-header {
495 |         display: flex;
496 |         justify-content: space-between;
497 |         align-items: center;
498 |         font-size: 13px;
499 |         font-weight: bold;
500 |         color: var(--el-color-primary);
501 |         margin-bottom: 10px;
502 |     }
503 | 
504 |     .preview-body {
505 |         display: flex;
506 |         gap: 12px;
507 |     }
508 | 
509 |     .preview-box {
510 |         flex: 1;
511 |         display: flex;
512 |         flex-direction: column;
513 |         background: var(--el-bg-color);
514 |         border: 1px solid var(--el-border-color-light);
515 |         border-radius: 6px;
516 |         padding: 8px;
517 |         min-height: 90px;
518 |     }
519 | 
520 |     .box-tag {
521 |         font-size: 11px;
522 |         color: var(--el-text-color-secondary);
523 |         margin-bottom: 6px;
524 |     }
525 | 
526 |     .realtime-img {
527 |         max-width: 100%;
528 |         max-height: 120px;
529 |         object-fit: contain;
530 |         border-radius: 4px;
531 |     }
532 | 
533 |     .placeholder {
534 |         content: "";
535 |         color: var(--el-text-color-placeholder);
536 |         font-size: 11px;
537 |         text-align: center;
538 |         margin: auto;
539 |     }
540 | 
541 |     .realtime-text {
542 |         font-size: 18px;
543 |         font-weight: bold;
544 |         color: #67C23A;
545 |         margin: auto;
546 |         word-break: break-all;
547 |         text-align: center;
548 |     }
549 | 
550 |         .realtime-text.empty {
551 |             color: var(--el-text-color-placeholder);
552 |             font-size: 12px;
553 |         }
554 | 
555 |     .stat-box {
556 |         align-items: center;
557 |         justify-content: center;
558 |     }
559 | 
560 |     .stat-score {
561 |         font-size: 28px;
562 |         font-weight: bold;
563 |         color: #F56C6C;
564 |         margin-bottom: 4px;
565 |     }
566 | 
567 |         .stat-score.pass {
568 |             color: var(--el-color-primary);
569 |         }
570 | 
571 |     .stat-detail {
572 |         display: flex;
573 |         flex-direction: column;
574 |         gap: 4px;
575 |         font-size: 11px;
576 |         color: var(--el-text-color-regular);
577 |         text-align: center;
578 |     }
579 | 
580 |     .save-actions {
581 |         margin-top: 20px;
582 |         display: flex;
583 |         justify-content: flex-end;
584 |     }
585 | 
586 |     .empty {
587 |         display: flex;
588 |         align-items: center;
589 |         justify-content: center;
590 |         height: 100%;
591 |         color: var(--el-text-color-secondary);
592 |     }
593 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\panels\NodeListPanel.vue

- Extension: .vue
- Language: unknown
- Size: 20066 bytes
- Created: 2026-07-28 20:52:08
- Modified: 2026-08-03 16:37:13

### Code

```unknown
  1 | <template>
  2 |     <div class="node-list-panel">
  3 |         <div class="panel-header">
  4 |             <span class="title">节点列表</span>
  5 |             <div class="header-actions">
  6 |                 <el-button size="small" :type="store.batchMode ? 'primary' : 'default'" @click="store.toggleBatchMode()">
  7 |                     {{ store.batchMode ? '退出批量' : '批量操作' }}
  8 |                 </el-button>
  9 |                 <el-dropdown @command="createNode">
 10 |                     <el-button size="small" type="primary"> + 新建 <el-icon><ArrowDown /></el-icon> </el-button>
 11 |                     <template #dropdown>
 12 |                         <el-dropdown-menu>
 13 |                             <el-dropdown-item v-for="(def, type) in store.params" :key="type" :command="type">
 14 |                                 {{ def.label || type }}
 15 |                             </el-dropdown-item>
 16 |                         </el-dropdown-menu>
 17 |                     </template>
 18 |                 </el-dropdown>
 19 |             </div>
 20 |         </div>
 21 | 
 22 |         <div v-if="store.batchMode" class="batch-toolbar">
 23 |             <el-checkbox :model-value="selectAll" @change="store.selectAllNodes()">全选</el-checkbox>
 24 |             <span class="batch-info">已选 {{ store.selectedNodeIds.length }} 个节点</span>
 25 |             <el-button size="small" @click="showBatchDelayDialog">⏱ 批量延迟</el-button>
 26 |             <el-button size="small" type="danger" @click="store.batchDeleteNodes()">🗑 批量删除</el-button>
 27 |         </div>
 28 | 
 29 |         <draggable v-model="store.nodes" item-key="node_id" class="node-list" handle=".drag-handle" @end="onDragEnd">
 30 |             <template #item="{ element: node, index }">
 31 |                 <div class="node-item" :class="{ active: store.selectedNodeId === node.node_id, 'batch-mode': store.batchMode }" @click="store.selectNode(node.node_id)">
 32 |                     <el-checkbox v-if="store.batchMode" :model-value="store.selectedNodeIds.includes(node.node_id)" @change.stop="store.toggleNodeSelection(node.node_id)" class="batch-checkbox" />
 33 | 
 34 |                     <!-- ⭐ 第一行：等待（居左） + 循环（居右） -->
 35 |                     <div class="node-row first-row">
 36 |                         <div class="left-group">
 37 |                             <el-icon><Timer /></el-icon>
 38 |                             <span class="label">延迟：</span>
 39 |                             <span v-if="editingDelay !== node.node_id" class="value" @dblclick="startEditDelay(node)">{{ node.delay_before }} ms</span>
 40 |                             <el-input v-else v-model="editDelayValue" size="small" type="number" @blur="finishEditDelay(node)" @keyup.enter="finishEditDelay(node)" class="inline-input" ref="delayInput" />
 41 |                             <el-button link size="small" class="edit-icon" @click.stop="startEditDelay(node)"><el-icon><Edit /></el-icon></el-button>
 42 |                         </div>
 43 |                         <div class="right-group">
 44 |                             <span class="label">循环：</span>
 45 |                             <span v-if="editingLoop !== node.node_id" class="value" @dblclick="startEditLoop(node)">{{ node.loop_count === -1 ? '无限' : node.loop_count }}</span>
 46 |                             <el-input v-else v-model="editLoopValue" size="small" type="number" @blur="finishEditLoop(node)" @keyup.enter="finishEditLoop(node)" class="inline-input" ref="loopInput" />
 47 |                             <el-button link size="small" class="edit-icon" @click.stop="startEditLoop(node)"><el-icon><Edit /></el-icon></el-button>
 48 |                         </div>
 49 |                     </div>
 50 | 
 51 |                     <!-- ⭐ 第二行：序号+类型图标+节点名（居左） + 拖动&更多操作（居右） -->
 52 |                     <div class="node-row second-row">
 53 |                         <div class="left-group">
 54 |                             <span class="index">{{ index + 1 }}.</span>
 55 |                             <el-icon class="node-icon" :style="{ color: getNodeColor(node.node_type) }"><component :is="getNodeIcon(node.node_type)" /></el-icon>
 56 |                             <span v-if="editingName !== node.node_id" class="node-name" @dblclick="startEditName(node)">{{ node.node_name }}</span>
 57 |                             <el-input v-else v-model="editNameValue" size="small" maxlength="10" @blur="finishEditName(node)" @keyup.enter="finishEditName(node)" class="inline-input" ref="nameInput" />
 58 |                             <el-button link size="small" class="edit-icon" @click.stop="startEditName(node)"><el-icon><Edit /></el-icon></el-button>
 59 |                         </div>
 60 |                         <div class="right-group" @click.stop>
 61 |                             <el-icon class="drag-handle"><Rank /></el-icon>
 62 |                             <el-dropdown @command="(cmd) => handleNodeMenu(cmd, node)">
 63 |                                 <el-button link size="small"><el-icon><More /></el-icon></el-button>
 64 |                                 <template #dropdown>
 65 |                                     <el-dropdown-menu>
 66 |                                         <el-dropdown-item command="run">▶ 从当前节点执行</el-dropdown-item>
 67 |                                         <el-dropdown-item command="disable">{{ node.enabled ? '⏸ 禁用节点' : '▶ 启用节点' }}</el-dropdown-item>
 68 |                                         <el-dropdown-item divided command="delete">🗑 删除节点</el-dropdown-item>
 69 |                                     </el-dropdown-menu>
 70 |                                 </template>
 71 |                             </el-dropdown>
 72 |                         </div>
 73 |                     </div>
 74 |                 </div>
 75 |             </template>
 76 |         </draggable>
 77 |         <div v-if="!store.nodes.length" class="empty">暂无节点</div>
 78 | 
 79 |         <el-dialog title="批量设置延迟" v-model="batchDelayDialog" width="400px" append-to-body>
 80 |             <el-form>
 81 |                 <el-form-item label="延迟(ms)">
 82 |                     <el-input-number v-model="batchDelayValue" :min="0" />
 83 |                 </el-form-item>
 84 |             </el-form>
 85 |             <template #footer>
 86 |                 <el-button @click="batchDelayDialog = false">取消</el-button>
 87 |                 <el-button type="primary" @click="confirmBatchDelay">确定</el-button>
 88 |             </template>
 89 |         </el-dialog>
 90 |     </div>
 91 | </template>
 92 | 
 93 | <script>
 94 |     import draggable from 'vuedraggable'
 95 |     import { useMainStore } from '@/stores'
 96 |     import { ElMessage, ElMessageBox } from 'element-plus'
 97 |     import { Timer, Edit, Rank, More, ArrowDown, Position, VideoPlay, Clock, Document, Grid, Folder, Search, Share, Setting, Reading, Operation } from '@element-plus/icons-vue'
 98 | 
 99 |     export default {
100 |         components: { draggable, Timer, Edit, Rank, More, ArrowDown, Position, VideoPlay, Clock, Document, Grid, Folder, Search, Share, Setting, Reading, Operation },
101 |         setup() {
102 |             const store = useMainStore()
103 |             return { store }
104 |         },
105 |         data() {
106 |             return {
107 |                 editingName: null, editNameValue: '',
108 |                 editingDelay: null, editDelayValue: '',
109 |                 editingLoop: null, editLoopValue: '',
110 |                 batchDelayDialog: false, batchDelayValue: 0
111 |             }
112 |         },
113 |         computed: {
114 |             selectAll: {
115 |                 get() {
116 |                     const nodes = this.store.nodes || []
117 |                     const selected = this.store.selectedNodeIds || []
118 |                     return nodes.length > 0 && selected.length === nodes.length
119 |                 },
120 |                 set() { this.store.selectAllNodes() }
121 |             }
122 |         },
123 |         watch: {
124 |             'store.batchMode'(val) { if (!val) this.store.selectedNodeIds = [] }
125 |         },
126 |         methods: {
127 |             getNodeIcon(type) {
128 |                 const map = {
129 |                     click: 'Position',
130 |                     wait: 'Clock',
131 |                     log: 'Document',
132 |                     set_window: 'Folder',
133 |                     image_recognition: 'Search',
134 |                     branch: 'Share',
135 |                     logic_check: 'Operation',
136 |                     ocr_recognition: 'Reading',
137 |                     variable_op: 'Setting',
138 |                     script_call: 'VideoPlay'
139 |                 }
140 |                 return map[type] || 'Document'
141 |             },
142 |             getNodeColor(type) {
143 |                 const map = {
144 |                     click: '#409EFF',
145 |                     wait: '#E6A23C',
146 |                     log: '#909399',
147 |                     set_window: '#67C23A',
148 |                     image_recognition: '#F56C6C',
149 |                     branch: '#9B59B6',
150 |                     logic_check: '#E67E22',
151 |                     ocr_recognition: '#3498DB',
152 |                     variable_op: '#1ABC9C',
153 |                     script_call: '#2ECC71'
154 |                 }
155 |                 return map[type] || '#909399'
156 |             },
157 |             startEditName(node) {
158 |                 this.editingName = node.node_id
159 |                 this.editNameValue = node.node_name
160 |                 this.$nextTick(() => { const input = this.$refs.nameInput; if (input) input.focus() })
161 |             },
162 |             finishEditName(node) {
163 |                 const name = this.editNameValue.trim()
164 |                 if (name.length > 10) { ElMessage.warning('节点名称不能超过10个字符'); this.editingName = null; return }
165 |                 if (name) { node.node_name = name; this.saveNode(node) }
166 |                 this.editingName = null
167 |             },
168 |             startEditDelay(node) {
169 |                 this.editingDelay = node.node_id; this.editDelayValue = node.delay_before
170 |                 this.$nextTick(() => { const input = this.$refs.delayInput; if (input) input.focus() })
171 |             },
172 |             finishEditDelay(node) {
173 |                 let val = parseInt(this.editDelayValue); if (isNaN(val) || val < 0) val = 0
174 |                 node.delay_before = val; this.saveNode(node); this.editingDelay = null
175 |             },
176 |             startEditLoop(node) {
177 |                 this.editingLoop = node.node_id; this.editLoopValue = node.loop_count
178 |                 this.$nextTick(() => { const input = this.$refs.loopInput; if (input) input.focus() })
179 |             },
180 |             finishEditLoop(node) {
181 |                 let val = parseInt(this.editLoopValue); if (isNaN(val) || val < -1) val = 1
182 |                 node.loop_count = val; this.saveNode(node); this.editingLoop = null
183 |             },
184 |             async saveNode(node) {
185 |                 try {
186 |                     const taskData = this.store.currentTaskData
187 |                     if (taskData) {
188 |                         const target = taskData.nodes.find(n => n.node_id === node.node_id)
189 |                         if (target) Object.assign(target, { node_name: node.node_name, delay_before: node.delay_before, loop_count: node.loop_count, enabled: node.enabled, params: node.params })
190 |                         await this.store.saveCurrentTask(true)
191 |                     }
192 |                 } catch (err) { console.error('保存节点失败', err); ElMessage.error('保存失败') }
193 |             },
194 |             async onDragEnd() {
195 |                 try {
196 |                     const taskData = this.store.currentTaskData
197 |                     if (taskData) { taskData.nodes = this.store.nodes; await this.store.saveCurrentTask(true) }
198 |                 } catch (err) { console.error('拖拽排序失败', err); ElMessage.error('保存顺序失败') }
199 |             },
200 |             handleNodeMenu(command, node) {
201 |                 switch (command) {
202 |                     case 'run': this.runFromNode(node); break
203 |                     case 'disable': node.enabled = !node.enabled; this.saveNode(node); break
204 |                     case 'delete': this.deleteNode(node); break
205 |                 }
206 |             },
207 |             async runFromNode(node) {
208 |                 const taskId = this.store.currentTaskId
209 |                 if (!taskId) {
210 |                     ElMessage.warning('请先选择一个任务')
211 |                     return
212 |                 }
213 |                 try {
214 |                     ElMessage.info(`从节点 ${node.node_name} 开始执行...`)
215 |                     const result = await this.store.runTask(taskId, node.node_id)
216 |                     if (result.status === 'started') {
217 |                         ElMessage.success('执行已启动')
218 |                     } else {
219 |                         ElMessage.error('执行失败: ' + (result.message || '未知错误'))
220 |                     }
221 |                 } catch (err) {
222 |                     ElMessage.error('执行请求失败: ' + (err.message || '未知错误'))
223 |                 }
224 |             },
225 |             async deleteNode(node) {
226 |                 try {
227 |                     await ElMessageBox.confirm(`确定要删除节点 "${node.node_name}" 吗？`, '确认删除', { type: 'warning' })
228 |                     const idx = this.store.nodes.findIndex(n => n.node_id === node.node_id)
229 |                     if (idx > -1) {
230 |                         this.store.nodes.splice(idx, 1)
231 |                         const taskData = this.store.currentTaskData
232 |                         if (taskData) { taskData.nodes = this.store.nodes; await this.store.saveCurrentTask(true) }
233 |                         if (this.store.selectedNodeId === node.node_id) this.store.selectNode(null)
234 |                         ElMessage.success('节点已删除')
235 |                     }
236 |                 } catch (err) { if (err !== 'cancel') console.error('删除失败', err) }
237 |             },
238 |             async createNode(nodeType) {
239 |                 const def = this.store.params[nodeType]
240 |                 if (!def) { ElMessage.warning(`未知节点类型: ${nodeType}`); return }
241 |                 const nodeId = `node_${Date.now()}`
242 |                 const newNode = {
243 |                     node_id: nodeId,
244 |                     node_name: def.label || nodeType,
245 |                     node_type: nodeType,
246 |                     params: {},
247 |                     delay_before: 0,
248 |                     loop_count: 1,
249 |                     enabled: true,
250 |                     on_success: { type: 'next', target: null, target_node: null, return_on_complete: false },
251 |                     on_failure: { type: 'next', target: null, target_node: null, return_on_complete: false },
252 |                     position: null
253 |                 }
254 |                 const nodeDefaults = this.store.params[nodeType]?.params || {}
255 |                 for (const [key, config] of Object.entries(nodeDefaults)) {
256 |                     if (config.type === 'list_int2' || config.type === 'list_int4') {
257 |                         newNode.params[key] = [0, 0, 0, 0].slice(0, config.type === 'list_int2' ? 2 : 4)
258 |                     } else if (config.type === 'list_dict') {
259 |                         newNode.params[key] = []
260 |                     } else if (config.type === 'dict') {
261 |                         const subDefaults = {}
262 |                         for (const [subKey, subConfig] of Object.entries(config.sub || {})) {
263 |                             if (subConfig.default !== undefined) {
264 |                                 if (Array.isArray(subConfig.default)) {
265 |                                     subDefaults[subKey] = [...subConfig.default]
266 |                                 } else {
267 |                                     subDefaults[subKey] = subConfig.default
268 |                                 }
269 |                             }
270 |                         }
271 |                         if (Object.keys(subDefaults).length) {
272 |                             newNode.params[key] = subDefaults
273 |                         }
274 |                     } else if (config.default !== undefined) {
275 |                         newNode.params[key] = config.default
276 |                     }
277 |                 }
278 |                 this.store.nodes.push(newNode)
279 |                 const taskData = this.store.currentTaskData
280 |                 if (taskData) { taskData.nodes = this.store.nodes; await this.store.saveCurrentTask(true) }
281 |                 ElMessage.success(`已添加节点: ${newNode.node_name}`)
282 |             },
283 |             showBatchDelayDialog() { this.batchDelayValue = 0; this.batchDelayDialog = true },
284 |             async confirmBatchDelay() { await this.store.batchSetDelay(this.batchDelayValue); this.batchDelayDialog = false }
285 |         }
286 |     }
287 | </script>
288 | 
289 | <style scoped>
290 |     .node-list-panel {
291 |         display: flex;
292 |         flex-direction: column;
293 |         height: 100%;
294 |         background: var(--el-bg-color);
295 |     }
296 | 
297 |     .panel-header {
298 |         padding: 8px 12px;
299 |         background: var(--el-fill-color-blank);
300 |         border-bottom: 1px solid var(--el-border-color-light);
301 |         display: flex;
302 |         justify-content: space-between;
303 |         align-items: center;
304 |         font-size: 13px;
305 |         font-weight: 600;
306 |         color: var(--el-text-color-primary);
307 |     }
308 | 
309 |     .header-actions {
310 |         display: flex;
311 |         gap: 6px;
312 |     }
313 | 
314 |     .batch-toolbar {
315 |         display: flex;
316 |         align-items: center;
317 |         gap: 8px;
318 |         padding: 6px 12px;
319 |         background: var(--el-fill-color-blank);
320 |         border-bottom: 1px solid var(--el-border-color-light);
321 |         font-size: 12px;
322 |     }
323 | 
324 |     .batch-info {
325 |         color: var(--el-color-primary);
326 |         font-weight: bold;
327 |     }
328 | 
329 |     .node-list {
330 |         flex: 1;
331 |         overflow-y: auto;
332 |         padding: 6px;
333 |         display: flex;
334 |         flex-direction: column;
335 |         gap: 6px;
336 |     }
337 | 
338 |     /* ⭐ 节点卡片容器：垂直两行布局 */
339 |     .node-item {
340 |         display: flex;
341 |         flex-direction: column;
342 |         gap: 6px;
343 |         padding: 8px 12px;
344 |         border-radius: 8px;
345 |         background: var(--el-fill-color-blank);
346 |         border: 1px solid var(--el-border-color-light);
347 |         cursor: pointer;
348 |         transition: all 0.2s ease;
349 |         user-select: none;
350 |         box-sizing: border-box;
351 |         width: 100%;
352 |     }
353 | 
354 |         .node-item:hover {
355 |             border-color: var(--el-color-primary);
356 |             background: var(--el-fill-color-light);
357 |         }
358 | 
359 |         .node-item.active {
360 |             border-color: var(--el-color-primary);
361 |             background: rgba(78, 209, 156, 0.15);
362 |         }
363 | 
364 |     /* ⭐⭐ 核心行样式：两端 100% 强行推开 */
365 |     .node-row {
366 |         display: flex !important;
367 |         justify-content: space-between !important;
368 |         align-items: center !important;
369 |         width: 100% !important;
370 |     }
371 | 
372 |     .left-group, .right-group {
373 |         display: flex;
374 |         align-items: center;
375 |         gap: 6px;
376 |     }
377 | 
378 |     /* 第一行：延迟与循环 */
379 |     .first-row .label {
380 |         font-size: 11px;
381 |         color: var(--el-text-color-secondary);
382 |     }
383 | 
384 |     .first-row .value {
385 |         font-size: 11px;
386 |         color: var(--el-text-color-regular);
387 |         font-weight: 500;
388 |     }
389 | 
390 |     /* 第二行：序号、名称与右侧操作栏 */
391 |     .second-row .index {
392 |         font-size: 13px;
393 |         font-weight: bold;
394 |         color: var(--el-text-color-secondary);
395 |     }
396 | 
397 |     .second-row .node-name {
398 |         font-size: 13px;
399 |         font-weight: 600;
400 |         color: var(--el-text-color-primary);
401 |     }
402 | 
403 |     .node-item.active .second-row .node-name {
404 |         color: var(--el-color-primary);
405 |     }
406 | 
407 |     .drag-handle {
408 |         cursor: move;
409 |         color: var(--el-text-color-secondary);
410 |         font-size: 14px;
411 |         user-select: none;
412 |         margin-left: 2px;
413 |     }
414 | 
415 |     .edit-icon {
416 |         padding: 0 !important;
417 |         height: auto !important;
418 |         font-size: 12px;
419 |         opacity: 0.6;
420 |     }
421 | 
422 |         .edit-icon:hover {
423 |             opacity: 1;
424 |         }
425 | 
426 |     .inline-input {
427 |         width: 70px;
428 |     }
429 | 
430 |     .empty {
431 |         text-align: center;
432 |         color: var(--el-text-color-placeholder);
433 |         font-size: 12px;
434 |         padding: 20px 0;
435 |     }
436 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\panels\PluginMarketPanel.vue

- Extension: .vue
- Language: unknown
- Size: 2093 bytes
- Created: 2026-08-10 12:09:40
- Modified: 2026-08-10 12:15:24

### Code

```unknown
 1 | <!-- frontend/src/components/panels/PluginMarketPanel.vue -->
 2 | <template>
 3 |     <div class="panel-container">
 4 |         <div class="panel-section-title">🧩 扩展插件中心</div>
 5 |         <div class="panel-body">
 6 |             <div class="plugin-item" v-for="p in plugins" :key="p.name">
 7 |                 <div class="p-info">
 8 |                     <span class="p-name">{{ p.name }}</span>
 9 |                     <span class="p-desc">{{ p.desc }}</span>
10 |                 </div>
11 |                 <el-button size="small" type="primary" plain>安装</el-button>
12 |             </div>
13 |         </div>
14 |     </div>
15 | </template>
16 | 
17 | <script setup>
18 | import { ref } from 'vue'
19 | const plugins = ref([
20 |   { name: 'OCR 增强插件', desc: '提供高精度离线文字识别支持' },
21 |   { name: 'ADB 远程控制', desc: '支持安卓模拟器多开同步点击' }
22 | ])
23 | </script>
24 | 
25 | <style scoped>
26 |     .panel-container {
27 |         height: 100%;
28 |         display: flex;
29 |         flex-direction: column;
30 |         background: var(--el-bg-color);
31 |         color: var(--el-text-color-regular);
32 |     }
33 | 
34 |     .panel-section-title {
35 |         padding: 10px 12px;
36 |         font-size: 12px;
37 |         font-weight: 600;
38 |         border-bottom: 1px solid var(--el-border-color-light);
39 |         color: var(--el-text-color-primary);
40 |     }
41 | 
42 |     .panel-body {
43 |         flex: 1;
44 |         padding: 10px;
45 |         overflow-y: auto;
46 |         display: flex;
47 |         flex-direction: column;
48 |         gap: 8px;
49 |     }
50 | 
51 |     .plugin-item {
52 |         display: flex;
53 |         justify-content: space-between;
54 |         align-items: center;
55 |         padding: 8px;
56 |         background: var(--el-fill-color-blank);
57 |         border-radius: 6px;
58 |         border: 1px solid var(--el-border-color-light);
59 |     }
60 | 
61 |     .p-info {
62 |         display: flex;
63 |         flex-direction: column;
64 |         gap: 2px;
65 |     }
66 | 
67 |     .p-name {
68 |         font-size: 12px;
69 |         font-weight: 600;
70 |         color: var(--el-text-color-primary);
71 |     }
72 | 
73 |     .p-desc {
74 |         font-size: 10px;
75 |         color: var(--el-text-color-secondary);
76 |     }
77 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\panels\ProjectExplorerPanel.vue

- Extension: .vue
- Language: unknown
- Size: 9361 bytes
- Created: 2026-08-10 12:09:25
- Modified: 2026-08-10 16:55:59

### Code

```unknown
  1 | <!-- frontend/src/components/panels/ProjectExplorerPanel.vue -->
  2 | <template>
  3 |     <div class="project-explorer-panel">
  4 |         <!-- 顶部项目路径信息 -->
  5 |         <div class="explorer-path-bar">
  6 |             <span class="path-label">项目:</span>
  7 |             <span class="path-value" :title="store.currentProjectPath">{{ projectFolderName }}</span>
  8 |         </div>
  9 | 
 10 |         <!-- 流程节点树 -->
 11 |         <div class="explorer-tree-body">
 12 |             <div v-if="tasksList.length === 0" class="empty-tree-tip">
 13 |                 <span>当前项目暂无任务组或节点</span>
 14 |             </div>
 15 | 
 16 |             <div v-for="(task, tIdx) in tasksList"
 17 |                  :key="task.task_id || tIdx"
 18 |                  class="task-group-item">
 19 |                 <!-- 1. 任务组 Header (第一层) -->
 20 |                 <div class="group-header"
 21 |                      :class="{ 'is-selected': isGroupSelected(task) }"
 22 |                      @click="handleGroupClick(task)">
 23 |                     <div class="header-left">
 24 |                         <span class="toggle-arrow" @click.stop="toggleGroupExpand(task.task_id || tIdx)">
 25 |                             <ChevronDown class="arrow-svg"
 26 |                                          :class="{ 'is-collapsed': collapsedGroups.includes(task.task_id || tIdx) }" />
 27 |                         </span>
 28 |                         <component :is="collapsedGroups.includes(task.task_id || tIdx) ? Folder : FolderOpen"
 29 |                                    class="group-icon" />
 30 |                         <span class="group-title">{{ task.task_name || `任务组 ${tIdx + 1}` }}</span>
 31 |                     </div>
 32 |                     <span class="node-count-badge">{{ (task.nodes || []).length }}</span>
 33 |                 </div>
 34 | 
 35 |                 <!-- 2. 节点列表 Body (第二层) -->
 36 |                 <div v-show="!collapsedGroups.includes(task.task_id || tIdx)"
 37 |                      class="node-list-container">
 38 |                     <div v-for="node in (task.nodes || [])"
 39 |                          :key="node.node_id"
 40 |                          class="node-tree-item"
 41 |                          :class="{ 'is-selected': isNodeSelected(node.node_id) }"
 42 |                          @click="handleNodeClick(node)">
 43 |                         <component :is="getNodeIcon(node.node_type)" class="node-icon" />
 44 |                         <span class="node-title">{{ node.node_name }}</span>
 45 |                     </div>
 46 | 
 47 |                     <div v-if="(task.nodes || []).length === 0" class="empty-group-tip">
 48 |                         组内无节点
 49 |                     </div>
 50 |                 </div>
 51 |             </div>
 52 |         </div>
 53 |     </div>
 54 | </template>
 55 | 
 56 | <script setup>
 57 |     import { ref, computed } from 'vue'
 58 |     import { useMainStore } from '@/stores'
 59 |     import {
 60 |         Folder, FolderOpen, ChevronDown, MousePointerClick, Clock,
 61 |         Image, ScanText, GitBranch, SearchCheck, Binary, ListOrdered, FileCode
 62 |     } from 'lucide-vue-next'
 63 | 
 64 |     const store = useMainStore()
 65 | 
 66 |     // 记录折叠状态的任务组 ID/索引
 67 |     const collapsedGroups = ref([])
 68 | 
 69 |     // 节图标类型映射
 70 |     const nodeIconComponentMap = {
 71 |         click: MousePointerClick,
 72 |         wait: Clock,
 73 |         image_recognition: Image,
 74 |         ocr_recognition: ScanText,
 75 |         branch: GitBranch,
 76 |         logic_check: SearchCheck,
 77 |         variable_op: Binary,
 78 |         log: ListOrdered,
 79 |         script_call: FileCode
 80 |     }
 81 |     const getNodeIcon = (type) => nodeIconComponentMap[type] || FileCode
 82 | 
 83 |     // 项目目录名
 84 |     const projectFolderName = computed(() => {
 85 |         const p = store.currentProjectPath || ''
 86 |         if (!p) return '未打开项目'
 87 |         return p.split(/[/\\]/).pop() || p
 88 |     })
 89 | 
 90 |     // 任务组与节点列表
 91 |     const tasksList = computed(() => {
 92 |         return store.blueprint?.tasks || []
 93 |     })
 94 | 
 95 |     // 判定组是否选中
 96 |     const isGroupSelected = (task) => {
 97 |         const groupId = `group_${task.task_id}`
 98 |         return store.selectedGroupId === groupId || store.selectedGroupId === task.task_id
 99 |     }
100 | 
101 |     // 判定节点是否选中
102 |     const isNodeSelected = (nodeId) => {
103 |         return (store.selectedNodeIds || []).includes(nodeId)
104 |     }
105 | 
106 |     // 点击展开/收起组
107 |     const toggleGroupExpand = (groupIdx) => {
108 |         const idx = collapsedGroups.value.indexOf(groupIdx)
109 |         if (idx > -1) {
110 |             collapsedGroups.value.splice(idx, 1)
111 |         } else {
112 |             collapsedGroups.value.push(groupIdx)
113 |         }
114 |     }
115 | 
116 |     // 点击组：选中组 + 驱动右侧 + 画布镜头对齐组中心
117 |     const handleGroupClick = (task) => {
118 |         const gId = `group_${task.task_id}`
119 |         store.selectedGroupId = gId
120 |         store.selectedNodeIds = []
121 | 
122 |         // 发发镜头聚焦事件
123 |         store.focusTarget = {
124 |             type: 'group',
125 |             id: gId,
126 |             timestamp: Date.now()
127 |         }
128 |     }
129 | 
130 |     // 点击节点：选中节点 + 驱动右侧 + 画布镜头对齐节点中心
131 |     const handleNodeClick = (node) => {
132 |         store.selectedNodeIds = [node.node_id]
133 |         store.selectedGroupId = null
134 | 
135 |         // 触发镜头聚焦事件
136 |         store.focusTarget = {
137 |             type: 'node',
138 |             id: node.node_id,
139 |             timestamp: Date.now()
140 |         }
141 |     }
142 | </script>
143 | 
144 | <style scoped>
145 |     .project-explorer-panel {
146 |         width: 100%;
147 |         height: 100%;
148 |         display: flex;
149 |         flex-direction: column;
150 |         background: var(--el-bg-color);
151 |         box-sizing: border-box;
152 |         user-select: none;
153 |         overflow: hidden;
154 |     }
155 | 
156 |     .explorer-path-bar {
157 |         padding: 8px 12px;
158 |         background: rgba(25, 26, 38, 0.95);
159 |         border-bottom: 1px solid var(--el-border-color-light);
160 |         display: flex;
161 |         align-items: center;
162 |         gap: 6px;
163 |         font-size: 11px;
164 |         flex-shrink: 0;
165 |     }
166 | 
167 |     .path-label {
168 |         color: var(--el-text-color-secondary);
169 |     }
170 | 
171 |     .path-value {
172 |         color: var(--el-color-primary);
173 |         font-weight: 600;
174 |         overflow: hidden;
175 |         text-overflow: ellipsis;
176 |         white-space: nowrap;
177 |     }
178 | 
179 |     .explorer-tree-body {
180 |         flex: 1;
181 |         padding: 8px;
182 |         overflow-y: auto;
183 |         display: flex;
184 |         flex-direction: column;
185 |         gap: 4px;
186 |     }
187 | 
188 |     .task-group-item {
189 |         display: flex;
190 |         flex-direction: column;
191 |     }
192 | 
193 |     /* 1. 组 Header 样式 */
194 |     .group-header {
195 |         padding: 6px 8px;
196 |         border-radius: 6px;
197 |         display: flex;
198 |         align-items: center;
199 |         justify-content: space-between;
200 |         cursor: pointer;
201 |         transition: background 0.2s;
202 |     }
203 | 
204 |         .group-header:hover {
205 |             background: var(--el-fill-color-light);
206 |         }
207 | 
208 |         .group-header.is-selected {
209 |             background: rgba(78, 209, 156, 0.15);
210 |             border: 1px solid rgba(78, 209, 156, 0.3);
211 |         }
212 | 
213 |     .header-left {
214 |         display: flex;
215 |         align-items: center;
216 |         gap: 6px;
217 |         overflow: hidden;
218 |     }
219 | 
220 |     .toggle-arrow {
221 |         display: flex;
222 |         align-items: center;
223 |         justify-content: center;
224 |         cursor: pointer;
225 |         color: var(--el-text-color-secondary);
226 |     }
227 | 
228 |     .arrow-svg {
229 |         width: 14px;
230 |         height: 14px;
231 |         transition: transform 0.2s ease;
232 |     }
233 | 
234 |         .arrow-svg.is-collapsed {
235 |             transform: rotate(-90deg);
236 |         }
237 | 
238 |     .group-icon {
239 |         width: 15px;
240 |         height: 15px;
241 |         color: #4ed19c;
242 |         flex-shrink: 0;
243 |     }
244 | 
245 |     .group-title {
246 |         font-size: 12px;
247 |         font-weight: 600;
248 |         color: var(--el-text-color-primary);
249 |         overflow: hidden;
250 |         text-overflow: ellipsis;
251 |         white-space: nowrap;
252 |     }
253 | 
254 |     .node-count-badge {
255 |         font-size: 10px;
256 |         background: rgba(255, 255, 255, 0.06);
257 |         color: var(--el-text-color-secondary);
258 |         padding: 1px 6px;
259 |         border-radius: 10px;
260 |     }
261 | 
262 |     /* 2. 节点树节点样式 */
263 |     .node-list-container {
264 |         display: flex;
265 |         flex-direction: column;
266 |         gap: 2px;
267 |         padding-left: 22px;
268 |         margin-top: 2px;
269 |     }
270 | 
271 |     .node-tree-item {
272 |         padding: 5px 8px;
273 |         border-radius: 4px;
274 |         display: flex;
275 |         align-items: center;
276 |         gap: 8px;
277 |         cursor: pointer;
278 |         transition: background 0.15s;
279 |     }
280 | 
281 |         .node-tree-item:hover {
282 |             background: var(--el-fill-color-light);
283 |         }
284 | 
285 |         .node-tree-item.is-selected {
286 |             background: var(--el-color-primary);
287 |             color: #ffffff;
288 |         }
289 | 
290 |     .node-icon {
291 |         width: 14px;
292 |         height: 14px;
293 |         flex-shrink: 0;
294 |     }
295 | 
296 |     .node-tree-item.is-selected .node-icon {
297 |         color: #ffffff;
298 |     }
299 | 
300 |     .node-title {
301 |         font-size: 12px;
302 |         overflow: hidden;
303 |         text-overflow: ellipsis;
304 |         white-space: nowrap;
305 |     }
306 | 
307 |     .empty-tree-tip, .empty-group-tip {
308 |         font-size: 11px;
309 |         color: var(--el-text-color-placeholder);
310 |         padding: 12px;
311 |         text-align: center;
312 |     }
313 | 
314 |     .empty-group-tip {
315 |         padding: 4px 8px;
316 |         text-align: left;
317 |     }
318 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\panels\TaskListPanel.vue

- Extension: .vue
- Language: unknown
- Size: 18416 bytes
- Created: 2026-07-28 22:38:54
- Modified: 2026-08-03 16:36:37

### Code

```unknown
  1 | <template>
  2 |     <div class="task-list-panel">
  3 |         <div class="panel-header">
  4 |             <span>任务列表</span>
  5 |             <el-button type="primary" size="small" circle @click="showNewTaskDialog">
  6 |                 <el-icon><Plus /></el-icon>
  7 |             </el-button>
  8 |         </div>
  9 | 
 10 |         <draggable v-model="sortedTasks"
 11 |                    item-key="task_id"
 12 |                    class="task-list"
 13 |                    handle=".drag-handle"
 14 |                    @end="onDragEnd">
 15 |             <template #item="{ element: task }">
 16 |                 <div class="task-card"
 17 |                      :class="{ active: store.currentTaskId === task.task_id }"
 18 |                      @click="selectTask(task.task_id)">
 19 |                     <!-- 第一行：任务名称 + 操作按钮 -->
 20 |                     <div class="task-row">
 21 |                         <div class="task-name-area">
 22 |                             <span v-if="editingName !== task.task_id" class="task-name" @dblclick="startEditName(task)">
 23 |                                 {{ task.task_name }}
 24 |                             </span>
 25 |                             <el-input v-else
 26 |                                       v-model="editNameValue"
 27 |                                       size="small"
 28 |                                       maxlength="10"
 29 |                                       @blur="finishEditName(task)"
 30 |                                       @keyup.enter="finishEditName(task)"
 31 |                                       class="inline-input"
 32 |                                       ref="nameInput" />
 33 |                             <el-button link
 34 |                                        size="small"
 35 |                                        class="edit-icon"
 36 |                                        @click.stop="startEditName(task)">
 37 |                                 <el-icon><Edit /></el-icon>
 38 |                             </el-button>
 39 |                         </div>
 40 |                         <div class="task-actions">
 41 |                             <el-button link size="small" class="action-icon play-btn" @click.stop="runTask(task.task_id)">
 42 |                                 <el-icon><VideoPlay /></el-icon>
 43 |                             </el-button>
 44 |                             <el-dropdown trigger="click" @command="(cmd) => handleMenuCommand(cmd, task)">
 45 |                                 <el-button link size="small" class="action-icon menu-btn">
 46 |                                     <el-icon><More /></el-icon>
 47 |                                 </el-button>
 48 |                                 <template #dropdown>
 49 |                                     <el-dropdown-menu>
 50 |                                         <el-dropdown-item command="rename">重命名</el-dropdown-item>
 51 |                                         <el-dropdown-item command="export">导出任务</el-dropdown-item>
 52 |                                         <el-dropdown-item divided command="delete">删除任务</el-dropdown-item>
 53 |                                     </el-dropdown-menu>
 54 |                                 </template>
 55 |                             </el-dropdown>
 56 |                             <el-icon class="drag-handle"><Rank /></el-icon>
 57 |                         </div>
 58 |                     </div>
 59 | 
 60 |                     <!-- 第二行：间隔（左） + 循环（右） -->
 61 |                     <div class="task-meta-row">
 62 |                         <div class="meta-item meta-left">
 63 |                             <span class="meta-label">间隔：</span>
 64 |                             <span v-if="editingInterval !== task.task_id" class="meta-value" @dblclick="startEditInterval(task)">
 65 |                                 {{ task.loop_interval || 0 }} ms
 66 |                             </span>
 67 |                             <el-input v-else
 68 |                                       v-model="editIntervalValue"
 69 |                                       size="small"
 70 |                                       type="number"
 71 |                                       @blur="finishEditInterval(task)"
 72 |                                       @keyup.enter="finishEditInterval(task)"
 73 |                                       class="inline-input"
 74 |                                       ref="intervalInput" />
 75 |                             <el-button link
 76 |                                        size="small"
 77 |                                        class="meta-edit-icon"
 78 |                                        @click.stop="startEditInterval(task)">
 79 |                                 <el-icon><Edit /></el-icon>
 80 |                             </el-button>
 81 |                         </div>
 82 |                         <div class="meta-item meta-right">
 83 |                             <span class="meta-label">循环：</span>
 84 |                             <span v-if="editingLoop !== task.task_id" class="meta-value" @dblclick="startEditLoop(task)">
 85 |                                 {{ task.loop_count === -1 ? '无限' : (task.loop_count ?? 1) + ' 次' }}
 86 |                             </span>
 87 |                             <el-input v-else
 88 |                                       v-model="editLoopValue"
 89 |                                       size="small"
 90 |                                       type="number"
 91 |                                       @blur="finishEditLoop(task)"
 92 |                                       @keyup.enter="finishEditLoop(task)"
 93 |                                       class="inline-input"
 94 |                                       ref="loopInput" />
 95 |                             <el-button link
 96 |                                        size="small"
 97 |                                        class="meta-edit-icon"
 98 |                                        @click.stop="startEditLoop(task)">
 99 |                                 <el-icon><Edit /></el-icon>
100 |                             </el-button>
101 |                         </div>
102 |                     </div>
103 |                 </div>
104 |             </template>
105 |         </draggable>
106 | 
107 |         <div v-if="!sortedTasks.length" class="empty">暂无任务</div>
108 | 
109 |         <el-dialog title="新建任务" v-model="dialogVisible" width="400px" append-to-body>
110 |             <el-form>
111 |                 <el-form-item label="任务名称">
112 |                     <el-input v-model="newTaskName" placeholder="最多10个字符" maxlength="10" @keyup.enter="confirmNewTask" />
113 |                 </el-form-item>
114 |             </el-form>
115 |             <template #footer>
116 |                 <el-button @click="dialogVisible = false">取消</el-button>
117 |                 <el-button type="primary" @click="confirmNewTask">创建</el-button>
118 |             </template>
119 |         </el-dialog>
120 |     </div>
121 | </template>
122 | 
123 | <script>
124 |     import draggable from 'vuedraggable'
125 |     import { useMainStore } from '@/stores'
126 |     import { ElMessage, ElMessageBox } from 'element-plus'
127 |     import axios from 'axios'
128 |     import { Plus, Edit, VideoPlay, More, Rank } from '@element-plus/icons-vue'
129 | 
130 |     export default {
131 |         components: { draggable, Plus, Edit, VideoPlay, More, Rank },
132 |         setup() {
133 |             const store = useMainStore()
134 |             return { store }
135 |         },
136 |         data() {
137 |             return {
138 |                 dialogVisible: false,
139 |                 newTaskName: '',
140 |                 editingName: null,
141 |                 editNameValue: '',
142 |                 editingInterval: null,
143 |                 editIntervalValue: '',
144 |                 editingLoop: null,
145 |                 editLoopValue: '',
146 |             }
147 |         },
148 |         computed: {
149 |             sortedTasks: {
150 |                 get() {
151 |                     const order = this.store.taskOrder || []
152 |                     if (order.length) {
153 |                         const tasksCopy = [...this.store.tasks]
154 |                         tasksCopy.sort((a, b) => {
155 |                             const idxA = order.indexOf(a.task_id)
156 |                             const idxB = order.indexOf(b.task_id)
157 |                             return (idxA === -1 ? 999 : idxA) - (idxB === -1 ? 999 : idxB)
158 |                         })
159 |                         return tasksCopy
160 |                     }
161 |                     return this.store.tasks || []
162 |                 },
163 |                 set(value) {
164 |                     this.store.tasks.splice(0, this.store.tasks.length, ...value)
165 |                     this.store.taskOrder = value.map(t => t.task_id)
166 |                 }
167 |             }
168 |         },
169 |         methods: {
170 |             async selectTask(taskId) {
171 |                 await this.store.loadTaskData(taskId)
172 |             },
173 |             async persistTaskChange(taskObj) {
174 |                 try {
175 |                     if (taskObj.task_id === this.store.currentTaskId && this.store.currentTaskData) {
176 |                         this.store.currentTaskData.task_name = taskObj.task_name
177 |                         this.store.currentTaskData.loop_interval = taskObj.loop_interval
178 |                         this.store.currentTaskData.loop_count = taskObj.loop_count
179 |                     }
180 |                     const res = await axios.get(`/api/tasks/${taskObj.task_id}`, {
181 |                         params: { project_path: this.store.currentProjectPath }
182 |                     })
183 |                     const fullTaskData = res.data
184 |                     fullTaskData.task_name = taskObj.task_name
185 |                     fullTaskData.loop_interval = taskObj.loop_interval
186 |                     fullTaskData.loop_count = taskObj.loop_count
187 | 
188 |                     await this.store.saveTaskData(fullTaskData)
189 |                     ElMessage.success('任务属性更新成功')
190 |                 } catch (err) {
191 |                     ElMessage.error('更新任务属性失败')
192 |                 }
193 |             },
194 |             startEditName(task) {
195 |                 this.editingName = task.task_id
196 |                 this.editNameValue = task.task_name
197 |                 this.$nextTick(() => {
198 |                     const input = this.$refs.nameInput
199 |                     if (input) input.focus()
200 |                 })
201 |             },
202 |             async finishEditName(task) {
203 |                 const name = this.editNameValue.trim()
204 |                 if (name.length > 10) {
205 |                     ElMessage.warning('任务名称不能超过10个字符')
206 |                     this.editingName = null
207 |                     return
208 |                 }
209 |                 if (name && name !== task.task_name) {
210 |                     task.task_name = name
211 |                     await this.persistTaskChange(task)
212 |                 }
213 |                 this.editingName = null
214 |             },
215 |             startEditInterval(task) {
216 |                 this.editingInterval = task.task_id
217 |                 this.editIntervalValue = task.loop_interval || 0
218 |                 this.$nextTick(() => {
219 |                     const input = this.$refs.intervalInput
220 |                     if (input) input.focus()
221 |                 })
222 |             },
223 |             async finishEditInterval(task) {
224 |                 let val = parseInt(this.editIntervalValue)
225 |                 if (isNaN(val) || val < 0) val = 0
226 |                 if (val !== task.loop_interval) {
227 |                     task.loop_interval = val
228 |                     await this.persistTaskChange(task)
229 |                 }
230 |                 this.editingInterval = null
231 |             },
232 |             startEditLoop(task) {
233 |                 this.editingLoop = task.task_id
234 |                 this.editLoopValue = task.loop_count
235 |                 this.$nextTick(() => {
236 |                     const input = this.$refs.loopInput
237 |                     if (input) input.focus()
238 |                 })
239 |             },
240 |             async finishEditLoop(task) {
241 |                 let val = parseInt(this.editLoopValue)
242 |                 if (isNaN(val) || val < -1) val = 1
243 |                 if (val !== task.loop_count) {
244 |                     task.loop_count = val
245 |                     await this.persistTaskChange(task)
246 |                 }
247 |                 this.editingLoop = null
248 |             },
249 |             async deleteTask(taskId) {
250 |                 const targetId = taskId || this.store.currentTaskId
251 |                 if (!targetId) return
252 |                 try {
253 |                     await ElMessageBox.confirm('确定要删除当前任务吗？', '确认删除', { type: 'warning' })
254 |                     await this.store.deleteTask(targetId)
255 |                     ElMessage.success('任务已删除')
256 |                 } catch (err) {
257 |                     if (err !== 'cancel') {
258 |                         ElMessage.error('删除失败: ' + (err.message || '未知错误'))
259 |                     }
260 |                 }
261 |             },
262 |             showNewTaskDialog() {
263 |                 this.newTaskName = ''
264 |                 this.dialogVisible = true
265 |             },
266 |             async confirmNewTask() {
267 |                 const name = this.newTaskName.trim()
268 |                 if (!name) {
269 |                     ElMessage.warning('请输入任务名称')
270 |                     return
271 |                 }
272 |                 if (name.length > 10) {
273 |                     ElMessage.warning('任务名称不能超过10个字符')
274 |                     return
275 |                 }
276 |                 try {
277 |                     await this.store.createNewTask(name)
278 |                     ElMessage.success('任务创建成功')
279 |                     this.dialogVisible = false
280 |                 } catch (err) {
281 |                     ElMessage.error(err.message || '创建失败')
282 |                 }
283 |             },
284 |             handleMenuCommand(command, task) {
285 |                 switch (command) {
286 |                     case 'rename':
287 |                         this.startEditName(task)
288 |                         break
289 |                     case 'export':
290 |                         ElMessage.info('导出任务')
291 |                         break
292 |                     case 'delete':
293 |                         this.deleteTask(task.task_id)
294 |                         break
295 |                 }
296 |             },
297 |             async runTask(taskId) {
298 |                 try {
299 |                     ElMessage.info('任务执行中...')
300 |                     const result = await this.store.runTask(taskId, null)
301 |                     if (result.status === 'started') {
302 |                         ElMessage.success('任务已启动，请查看执行状态')
303 |                     } else {
304 |                         ElMessage.error('执行失败: ' + (result.message || '未知错误'))
305 |                     }
306 |                 } catch (err) {
307 |                     ElMessage.error('执行请求失败: ' + (err.message || '未知错误'))
308 |                 }
309 |             },
310 |             async onDragEnd() {
311 |                 const order = this.store.tasks.map(t => t.task_id)
312 |                 await this.store.saveTaskOrder(order)
313 |                 ElMessage.success('任务顺序已保存')
314 |             }
315 |         }
316 |     }
317 | </script>
318 | 
319 | <style scoped>
320 |     .task-list-panel {
321 |         display: flex;
322 |         flex-direction: column;
323 |         height: 100%;
324 |         background: var(--el-bg-color);
325 |     }
326 | 
327 |     .panel-header {
328 |         padding: 8px 12px;
329 |         background: var(--el-fill-color-blank);
330 |         border-bottom: 1px solid var(--el-border-color-light);
331 |         display: flex;
332 |         justify-content: space-between;
333 |         align-items: center;
334 |         font-size: 13px;
335 |         font-weight: 600;
336 |         color: var(--el-text-color-primary);
337 |     }
338 | 
339 |     .task-list {
340 |         flex: 1;
341 |         overflow-y: auto;
342 |         padding: 6px;
343 |         display: flex;
344 |         flex-direction: column;
345 |         gap: 6px;
346 |     }
347 | 
348 |     /* 任务卡片容器：上下分行 */
349 |     .task-card {
350 |         display: flex;
351 |         flex-direction: column;
352 |         gap: 6px;
353 |         padding: 8px 12px;
354 |         border-radius: 8px;
355 |         background: var(--el-fill-color-blank);
356 |         border: 1px solid var(--el-border-color-light);
357 |         cursor: pointer;
358 |         transition: all 0.2s ease;
359 |         box-sizing: border-box;
360 |         width: 100%;
361 |     }
362 | 
363 |         .task-card:hover {
364 |             border-color: var(--el-color-primary);
365 |             background: var(--el-fill-color-light);
366 |         }
367 | 
368 |         .task-card.active {
369 |             border-color: var(--el-color-primary);
370 |             background: rgba(78, 209, 156, 0.12);
371 |         }
372 | 
373 |     /* ⭐ 第一行样式：强行两端推开 (Left/Right) */
374 |     .task-row {
375 |         display: flex !important;
376 |         justify-content: space-between !important;
377 |         align-items: center !important;
378 |         width: 100% !important;
379 |     }
380 | 
381 |     .task-name-area {
382 |         display: flex;
383 |         align-items: center;
384 |         gap: 6px;
385 |         font-size: 14px;
386 |         font-weight: 600;
387 |         color: var(--el-text-color-primary);
388 |         flex: 1;
389 |         overflow: hidden;
390 |     }
391 | 
392 |     .task-name {
393 |         white-space: nowrap;
394 |         overflow: hidden;
395 |         text-overflow: ellipsis;
396 |     }
397 | 
398 |     .task-card.active .task-name {
399 |         color: var(--el-color-primary);
400 |     }
401 | 
402 |     .task-actions {
403 |         display: flex;
404 |         align-items: center;
405 |         gap: 6px;
406 |         flex-shrink: 0;
407 |     }
408 | 
409 |     .edit-icon, .meta-edit-icon {
410 |         padding: 0 !important;
411 |         height: auto !important;
412 |         font-size: 12px;
413 |         opacity: 0.6;
414 |     }
415 | 
416 |         .edit-icon:hover, .meta-edit-icon:hover {
417 |             opacity: 1;
418 |         }
419 | 
420 |     .play-btn {
421 |         color: var(--el-color-primary) !important;
422 |         font-size: 16px;
423 |     }
424 | 
425 |     .drag-handle {
426 |         cursor: move;
427 |         color: var(--el-text-color-secondary);
428 |         font-size: 14px;
429 |         user-select: none;
430 |         margin-left: 2px;
431 |     }
432 | 
433 |     /* ⭐ 第二行样式：间隔（居左） + 循环（居右） */
434 |     .task-meta-row {
435 |         display: flex !important;
436 |         justify-content: space-between !important;
437 |         align-items: center !important;
438 |         width: 100% !important;
439 |         font-size: 11px;
440 |         color: var(--el-text-color-secondary);
441 |     }
442 | 
443 |     .meta-item {
444 |         display: flex;
445 |         align-items: center;
446 |         gap: 4px;
447 |     }
448 | 
449 |     .meta-value {
450 |         color: var(--el-text-color-regular);
451 |         font-weight: 500;
452 |     }
453 | 
454 |     .inline-input {
455 |         width: 80px;
456 |     }
457 | 
458 |     .empty {
459 |         text-align: center;
460 |         color: var(--el-text-color-placeholder);
461 |         font-size: 12px;
462 |         padding: 20px 0;
463 |     }
464 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\shell\ActivityBar.vue

- Extension: .vue
- Language: unknown
- Size: 2961 bytes
- Created: 2026-08-10 11:16:03
- Modified: 2026-08-10 12:00:40

### Code

```unknown
  1 | ﻿<!-- frontend/src/components/shell/ActivityBar.vue -->
  2 | <template>
  3 |     <div class="activity-bar" :class="position">
  4 |         <el-tooltip v-for="item in items"
  5 |                     :key="item.id"
  6 |                     effect="dark"
  7 |                     :content="item.title"
  8 |                     placement="right"
  9 |                     :show-after="300"
 10 |                     popper-class="ide-sidebar-tooltip">
 11 |             <div class="activity-icon-item"
 12 |                  :class="{ 'is-active': activeId === item.id }"
 13 |                  @click="$emit('select', item.id)">
 14 |                 <component :is="item.icon" class="act-svg" />
 15 |             </div>
 16 |         </el-tooltip>
 17 |     </div>
 18 | </template>
 19 | 
 20 | <script setup>
 21 |     defineProps({
 22 |         items: { type: Array, default: () => [] },
 23 |         activeId: { type: String, default: null },
 24 |         position: { type: String, default: 'left' } // left | right | bottom
 25 |     })
 26 | 
 27 |     defineEmits(['select'])
 28 | </script>
 29 | 
 30 | <style scoped>
 31 |     .activity-bar {
 32 |         background: #181926;
 33 |         display: flex;
 34 |         align-items: center;
 35 |         flex-shrink: 0;
 36 |         z-index: 50;
 37 |         user-select: none;
 38 |     }
 39 | 
 40 |         .activity-bar.left, .activity-bar.right {
 41 |             width: 40px;
 42 |             height: 100%;
 43 |             flex-direction: column;
 44 |             padding-top: 6px;
 45 |             gap: 4px;
 46 |         }
 47 | 
 48 |         .activity-bar.bottom {
 49 |             height: 40px;
 50 |             width: 100%;
 51 |             flex-direction: row;
 52 |             padding-left: 6px;
 53 |             gap: 4px;
 54 |         }
 55 | 
 56 |     .activity-icon-item {
 57 |         width: 32px;
 58 |         height: 32px;
 59 |         margin: 0 auto;
 60 |         border-radius: 6px;
 61 |         display: flex;
 62 |         align-items: center;
 63 |         justify-content: center;
 64 |         cursor: pointer;
 65 |         color: var(--el-text-color-secondary);
 66 |         transition: all 0.2s ease;
 67 |     }
 68 | 
 69 |         .activity-icon-item:hover {
 70 |             background: var(--el-fill-color-light);
 71 |             color: var(--el-text-color-primary);
 72 |         }
 73 | 
 74 |         .activity-icon-item.is-active {
 75 |             background: rgba(78, 209, 156, 0.15);
 76 |             color: var(--el-color-primary);
 77 |         }
 78 | 
 79 |     .act-svg {
 80 |         width: 18px;
 81 |         height: 18px;
 82 |     }
 83 | </style>
 84 | 
 85 | <!-- ⚡ 全局 Popper 气泡美化样式（必须为非 scoped，才能精确修饰 Element Plus 的浮动提示框） -->
 86 | <style>
 87 |     .el-popper.ide-sidebar-tooltip {
 88 |         background: #252536 !important;
 89 |         border: 1px solid #353757 !important;
 90 |         color: #ffffff !important;
 91 |         font-size: 12px !important;
 92 |         padding: 6px 10px !important;
 93 |         border-radius: 6px !important;
 94 |         box-shadow: 0 6px 20px rgba(0, 0, 0, 0.5) !important;
 95 |     }
 96 | 
 97 |         .el-popper.ide-sidebar-tooltip .el-popper__arrow::before {
 98 |             background: #252536 !important;
 99 |             border: 1px solid #353757 !important;
100 |         }
101 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\components\shell\TopMenuBar.vue

- Extension: .vue
- Language: unknown
- Size: 6624 bytes
- Created: 2026-08-10 11:15:56
- Modified: 2026-08-10 11:23:42

### Code

```unknown
  1 | ﻿<!-- frontend/src/components/shell/TopMenuBar.vue -->
  2 | <template>
  3 |     <div class="top-menu-bar">
  4 |         <div class="menu-brand">
  5 |             <span class="brand-logo">⚡</span>
  6 |             <span class="brand-title">Easycode IDE</span>
  7 |         </div>
  8 | 
  9 |         <div class="menu-items-group">
 10 |             <el-dropdown trigger="click" @command="handleMenuCommand">
 11 |                 <span class="menu-label">文件 (F)</span>
 12 |                 <template #dropdown>
 13 |                     <el-dropdown-menu>
 14 |                         <el-dropdown-item command="open">打开项目...</el-dropdown-item>
 15 |                         <el-dropdown-item command="save" divided>保存蓝图</el-dropdown-item>
 16 |                         <el-dropdown-item command="export">导出配置</el-dropdown-item>
 17 |                     </el-dropdown-menu>
 18 |                 </template>
 19 |             </el-dropdown>
 20 | 
 21 |             <el-dropdown trigger="click" @command="handleMenuCommand">
 22 |                 <span class="menu-label">编辑 (E)</span>
 23 |                 <template #dropdown>
 24 |                     <el-dropdown-menu>
 25 |                         <el-dropdown-item command="undo">撤销</el-dropdown-item>
 26 |                         <el-dropdown-item command="redo">重做</el-dropdown-item>
 27 |                         <el-dropdown-item command="batch" divided>批量操作</el-dropdown-item>
 28 |                     </el-dropdown-menu>
 29 |                 </template>
 30 |             </el-dropdown>
 31 | 
 32 |             <el-dropdown trigger="click" @command="handleMenuCommand">
 33 |                 <span class="menu-label">视图 (V)</span>
 34 |                 <template #dropdown>
 35 |                     <el-dropdown-menu>
 36 |                         <el-dropdown-item command="toggle_minimap">切换全景导航</el-dropdown-item>
 37 |                         <el-dropdown-item command="toggle_log">切换运行日志</el-dropdown-item>
 38 |                     </el-dropdown-menu>
 39 |                 </template>
 40 |             </el-dropdown>
 41 | 
 42 |             <el-dropdown trigger="click" @command="handleMenuCommand">
 43 |                 <span class="menu-label">运行 (R)</span>
 44 |                 <template #dropdown>
 45 |                     <el-dropdown-menu>
 46 |                         <el-dropdown-item command="run_task">▶ 运行当前任务</el-dropdown-item>
 47 |                         <el-dropdown-item command="screenshot">📷 截图工具</el-dropdown-item>
 48 |                     </el-dropdown-menu>
 49 |                 </template>
 50 |             </el-dropdown>
 51 | 
 52 |             <el-dropdown trigger="click" @command="handleMenuCommand">
 53 |                 <span class="menu-label">帮助 (H)</span>
 54 |                 <template #dropdown>
 55 |                     <el-dropdown-menu>
 56 |                         <el-dropdown-item command="docs">官方文档</el-dropdown-item>
 57 |                         <el-dropdown-item command="about">关于 Easycode</el-dropdown-item>
 58 |                     </el-dropdown-menu>
 59 |                 </template>
 60 |             </el-dropdown>
 61 |         </div>
 62 | 
 63 |         <!-- 右侧操作区：工作面板胶囊 + 运行按钮 -->
 64 |         <div class="menu-right-actions">
 65 |             <div class="workspace-switcher-badge" @click="$emit('openSettings')">
 66 |                 <span class="device-icon">💻</span>
 67 |                 <span class="workspace-label">工作面板:</span>
 68 |                 <span class="workspace-name">{{ currentWorkspaceName }}</span>
 69 |                 <span class="dropdown-arrow">▼</span>
 70 |             </div>
 71 | 
 72 |             <el-button type="success" size="small" class="run-quick-btn" @click="$emit('run')">
 73 |                 ▶ 运行
 74 |             </el-button>
 75 |         </div>
 76 |     </div>
 77 | </template>
 78 | 
 79 | <script setup>
 80 |     import { computed } from 'vue'
 81 |     import { useMainStore } from '@/stores'
 82 |     import { ElMessage } from 'element-plus'
 83 | 
 84 |     const store = useMainStore()
 85 |     defineEmits(['run', 'openSettings'])
 86 | 
 87 |     const currentWorkspaceName = computed(() => {
 88 |         const ctx = store.currentContext
 89 |         if (ctx && ctx.windowTitle) {
 90 |             return ctx.windowTitle
 91 |         }
 92 |         return 'Windows 桌面'
 93 |     })
 94 | 
 95 |     const handleMenuCommand = (command) => {
 96 |         if (command === 'toggle_minimap') store.toggleMinimap()
 97 |         if (command === 'toggle_log') store.toggleLogPanel()
 98 |         if (command === 'about') ElMessage.info('Easycode Automation Studio v2.2')
 99 |     }
100 | </script>
101 | 
102 | <style scoped>
103 |     .top-menu-bar {
104 |         height: 40px;
105 |         background: var(--el-bg-color);
106 |         border-bottom: 1px solid var(--el-border-color-light);
107 |         display: flex;
108 |         align-items: center;
109 |         padding: 0 12px;
110 |         gap: 16px;
111 |         flex-shrink: 0;
112 |         user-select: none;
113 |         font-size: 12px;
114 |     }
115 | 
116 |     .menu-brand {
117 |         display: flex;
118 |         align-items: center;
119 |         gap: 6px;
120 |         font-weight: bold;
121 |         color: var(--el-color-primary);
122 |     }
123 | 
124 |     .brand-logo {
125 |         font-size: 14px;
126 |     }
127 | 
128 |     .menu-items-group {
129 |         display: flex;
130 |         gap: 12px;
131 |     }
132 | 
133 |     .menu-label {
134 |         color: var(--el-text-color-regular);
135 |         cursor: pointer;
136 |         padding: 4px 8px;
137 |         border-radius: 4px;
138 |         transition: background 0.2s;
139 |     }
140 | 
141 |         .menu-label:hover {
142 |             background: var(--el-fill-color-light);
143 |             color: var(--el-text-color-primary);
144 |         }
145 | 
146 |     .menu-right-actions {
147 |         margin-left: auto;
148 |         display: flex;
149 |         align-items: center;
150 |         gap: 12px;
151 |     }
152 | 
153 |     .workspace-switcher-badge {
154 |         display: flex;
155 |         align-items: center;
156 |         gap: 6px;
157 |         background: rgba(25, 26, 38, 0.85);
158 |         border: 1px solid var(--el-border-color-light);
159 |         padding: 2px 10px;
160 |         border-radius: 14px;
161 |         font-size: 11px;
162 |         cursor: pointer;
163 |         transition: all 0.2s ease;
164 |         user-select: none;
165 |         height: 26px;
166 |     }
167 | 
168 |         .workspace-switcher-badge:hover {
169 |             border-color: var(--el-color-primary);
170 |             background: rgba(38, 40, 61, 0.95);
171 |         }
172 | 
173 |     .device-icon {
174 |         font-size: 11px;
175 |     }
176 | 
177 |     .workspace-label {
178 |         color: var(--el-text-color-secondary);
179 |     }
180 | 
181 |     .workspace-name {
182 |         color: var(--el-color-primary);
183 |         font-weight: 600;
184 |     }
185 | 
186 |     .dropdown-arrow {
187 |         font-size: 8px;
188 |         color: var(--el-text-color-secondary);
189 |         margin-left: 2px;
190 |     }
191 | 
192 |     .run-quick-btn {
193 |         height: 26px !important;
194 |         padding: 0 12px !important;
195 |         font-size: 12px !important;
196 |     }
197 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\composables\useCanvasDrag.js

- Extension: .js
- Language: javascript
- Size: 8662 bytes
- Created: 2026-08-06 10:33:09
- Modified: 2026-08-06 10:34:25

### Code

```javascript
  1 | import { ref, reactive } from 'vue'
  2 | import { ElMessage } from 'element-plus'
  3 | import axios from 'axios'
  4 | 
  5 | export function useCanvasDrag(store, renderNodes, dynamicGroups, viewport, GRID_SIZE, NODE_GRID_W, NODE_GRID_H) {
  6 |     const localDraftPositions = reactive({})
  7 |     const draggingNodeId = ref(null)
  8 |     const dragStartMouse = ref({ x: 0, y: 0 })
  9 |     const nodeInitialPos = ref({ x: 0, y: 0 })
 10 |     const hasMoved = ref(false)
 11 |     const isCtrlHeldRef = ref(false)
 12 | 
 13 |     const draggedSourceGroupSnapshot = ref(null)
 14 |     const ghostPlaceholder = ref(null)
 15 |     const dragPreviewBox = ref({ visible: false, x: 0, y: 0, w: 0, h: 0, hasCollision: false })
 16 | 
 17 |     const calculateOverlapRatio = (rectA, rectB) => {
 18 |         if (!rectA || !rectB) return 0
 19 |         const xOverlap = Math.max(0, Math.min(rectA.x + rectA.w, rectB.x + rectB.w) - Math.max(rectA.x, rectB.x))
 20 |         const yOverlap = Math.max(0, Math.min(rectA.y + rectA.h, rectB.y + rectB.h) - Math.max(rectA.y, rectB.y))
 21 |         const intersectionArea = xOverlap * yOverlap
 22 |         const areaA = rectA.w * rectA.h
 23 |         if (areaA <= 0) return 0
 24 |         return intersectionArea / areaA
 25 |     }
 26 | 
 27 |     const resolveCollisionsAndPushOthers = (targetNodeId, dropPos, allNodes, nodeSize) => {
 28 |         const MIN_GAP = 2 * GRID_SIZE
 29 |         const stepW = nodeSize.w + MIN_GAP
 30 |         const stepH = nodeSize.h + MIN_GAP
 31 | 
 32 |         let movingNodes = [{ id: targetNodeId, pos: { ...dropPos } }]
 33 |         localDraftPositions[targetNodeId] = { ...dropPos }
 34 | 
 35 |         let maxIterations = 15
 36 |         let iteration = 0
 37 | 
 38 |         while (iteration < maxIterations) {
 39 |             iteration++
 40 |             let hasNewCollision = false
 41 | 
 42 |             for (let i = 0; i < movingNodes.length; i++) {
 43 |                 const current = movingNodes[i]
 44 |                 const currPos = current.pos
 45 |                 const currSize = nodeSize
 46 | 
 47 |                 for (const other of allNodes) {
 48 |                     if (other.node_id === current.id) continue
 49 |                     if (movingNodes.some(m => m.id === other.node_id)) continue
 50 |                     if (ghostPlaceholder.value && other.node_id === ghostPlaceholder.value.node_id) continue
 51 | 
 52 |                     const otherPos = localDraftPositions[other.node_id] || other.position || { x: 0, y: 0 }
 53 |                     const otherSize = { w: other.w || nodeSize.w, h: other.h || nodeSize.h }
 54 | 
 55 |                     const isIntersect = !(
 56 |                         currPos.x + currSize.w + MIN_GAP <= otherPos.x ||
 57 |                         currPos.x >= otherPos.x + otherSize.w + MIN_GAP ||
 58 |                         currPos.y + currSize.h + MIN_GAP <= otherPos.y ||
 59 |                         currPos.y >= otherPos.y + otherSize.h + MIN_GAP
 60 |                     )
 61 | 
 62 |                     if (isIntersect) {
 63 |                         hasNewCollision = true
 64 |                         const currCenterX = currPos.x + currSize.w / 2
 65 |                         const otherCenterX = otherPos.x + otherSize.w / 2
 66 |                         const currCenterY = currPos.y + currSize.h / 2
 67 |                         const otherCenterY = otherPos.y + otherSize.h / 2
 68 | 
 69 |                         const dx = currCenterX - otherCenterX
 70 |                         const dy = currCenterY - otherCenterY
 71 | 
 72 |                         let nextPos = { ...otherPos }
 73 |                         if (Math.abs(dx) > Math.abs(dy)) {
 74 |                             nextPos.x = dx > 0 ? currPos.x - stepW : currPos.x + stepW
 75 |                         } else {
 76 |                             nextPos.y = dy > 0 ? currPos.y - stepH : currPos.y + stepH
 77 |                         }
 78 | 
 79 |                         nextPos.x = Math.round(nextPos.x / GRID_SIZE) * GRID_SIZE
 80 |                         nextPos.y = Math.round(nextPos.y / GRID_SIZE) * GRID_SIZE
 81 | 
 82 |                         localDraftPositions[other.node_id] = nextPos
 83 |                         other.position = nextPos
 84 |                         movingNodes.push({ id: other.node_id, pos: nextPos })
 85 |                     }
 86 |                 }
 87 |             }
 88 |             if (!hasNewCollision) break
 89 |         }
 90 |         return localDraftPositions[targetNodeId] || dropPos
 91 |     }
 92 | 
 93 |     const resolveGroupCollisionsAndPushOthers = (draggingTaskId, newBox, allGroups) => {
 94 |         const MIN_GROUP_GAP = GRID_SIZE
 95 |         let movingGroups = [{ id: draggingTaskId, box: { ...newBox } }]
 96 |         let adjustedBoxes = { [draggingTaskId]: { ...newBox } }
 97 | 
 98 |         let maxIterations = 10
 99 |         let iteration = 0
100 | 
101 |         while (iteration < maxIterations) {
102 |             iteration++
103 |             let hasNewCollision = false
104 | 
105 |             for (let i = 0; i < movingGroups.length; i++) {
106 |                 const current = movingGroups[i]
107 |                 const currBox = current.box
108 | 
109 |                 for (const other of allGroups) {
110 |                     if (other.taskId === current.id) continue
111 |                     if (movingGroups.some(m => m.id === other.taskId)) continue
112 | 
113 |                     const otherBox = adjustedBoxes[other.taskId] || other.box
114 |                     const isIntersect = !(
115 |                         currBox.x + currBox.w + MIN_GROUP_GAP <= otherBox.x ||
116 |                         currBox.x >= otherBox.x + otherBox.w + MIN_GROUP_GAP ||
117 |                         currBox.y + currBox.h + MIN_GROUP_GAP <= otherBox.y ||
118 |                         currBox.y >= otherBox.y + otherBox.h + MIN_GROUP_GAP
119 |                     )
120 | 
121 |                     if (isIntersect) {
122 |                         hasNewCollision = true
123 |                         const currCenterX = currBox.x + currBox.w / 2
124 |                         const otherCenterX = otherBox.x + otherBox.w / 2
125 |                         const currCenterY = currBox.y + currBox.h / 2
126 |                         const otherCenterY = otherBox.y + otherBox.h / 2
127 | 
128 |                         const dx = otherCenterX - currCenterX
129 |                         const dy = otherCenterY - currCenterY
130 |                         const overlapX = Math.min(currBox.x + currBox.w + MIN_GROUP_GAP - otherBox.x, otherBox.x + otherBox.w + MIN_GROUP_GAP - currBox.x)
131 |                         const overlapY = Math.min(currBox.y + currBox.h + MIN_GROUP_GAP - otherBox.y, otherBox.y + otherBox.h + MIN_GROUP_GAP - currBox.y)
132 | 
133 |                         let nextBox = { ...otherBox }
134 |                         if (overlapX < overlapY) {
135 |                             nextBox.x = dx > 0 ? currBox.x + currBox.w + MIN_GROUP_GAP : currBox.x - otherBox.w - MIN_GROUP_GAP
136 |                         } else {
137 |                             nextBox.y = dy > 0 ? currBox.y + currBox.h + MIN_GROUP_GAP : currBox.y - otherBox.h - MIN_GROUP_GAP
138 |                         }
139 | 
140 |                         nextBox.x = Math.round(nextBox.x / GRID_SIZE) * GRID_SIZE
141 |                         nextBox.y = Math.round(nextBox.y / GRID_SIZE) * GRID_SIZE
142 | 
143 |                         adjustedBoxes[other.taskId] = nextBox
144 |                         movingGroups.push({ id: other.taskId, box: nextBox })
145 |                     }
146 |                 }
147 |             }
148 |             if (!hasNewCollision) break
149 |         }
150 |         return adjustedBoxes
151 |     }
152 | 
153 |     const onNodeMouseDown = (e, node) => {
154 |         isCtrlHeldRef.value = e.ctrlKey
155 |         draggedSourceGroupSnapshot.value = null
156 |         ghostPlaceholder.value = null
157 | 
158 |         ghostPlaceholder.value = {
159 |             node_id: `ghost_${node.node_id}`,
160 |             position: { ...node.position },
161 |             w: NODE_GRID_W * GRID_SIZE,
162 |             h: NODE_GRID_H * GRID_SIZE
163 |         }
164 | 
165 |         const tasks = store.currentTaskData?.tasks || []
166 |         tasks.forEach((t, tIdx) => {
167 |             const found = (t.nodes || []).find(n => n.node_id === node.node_id)
168 |             if (found) {
169 |                 const groupInfo = dynamicGroups.value[tIdx]
170 |                 if (groupInfo && groupInfo.box) {
171 |                     draggedSourceGroupSnapshot.value = { ...groupInfo.box }
172 |                 }
173 |             }
174 |         })
175 | 
176 |         draggingNodeId.value = node.node_id
177 |         dragStartMouse.value = { x: e.clientX, y: e.clientY }
178 |         nodeInitialPos.value = node.position ? { ...node.position } : { x: 0, y: 0 }
179 |         hasMoved.value = false
180 |         e.stopPropagation()
181 |     }
182 | 
183 |     return {
184 |         localDraftPositions,
185 |         draggingNodeId,
186 |         dragStartMouse,
187 |         nodeInitialPos,
188 |         hasMoved,
189 |         isCtrlHeldRef,
190 |         draggedSourceGroupSnapshot,
191 |         ghostPlaceholder,
192 |         dragPreviewBox,
193 |         resolveCollisionsAndPushOthers,
194 |         resolveGroupCollisionsAndPushOthers,
195 |         calculateOverlapRatio,
196 |         onNodeMouseDown
197 |     }
198 | }
```

## File: D:\PycharmProjects\Easycode\frontend\src\composables\useCanvasEdges.js

- Extension: .js
- Language: javascript
- Size: 7669 bytes
- Created: 2026-08-06 10:33:01
- Modified: 2026-08-06 10:33:30

### Code

```javascript
  1 | import { computed } from 'vue'
  2 | import { router } from '@/utils/gridRouter'
  3 | import { getRoundedPathString } from '@/utils/pathSmooth'
  4 | 
  5 | export function useCanvasEdges(renderNodes, draggingNodeId, hasMoved, selectedEdgeId, drawingConnection) {
  6 |     const getArrowDirection = (points) => {
  7 |         if (!points || points.length < 2) return 'down'
  8 |         let p1 = points[points.length - 2]
  9 |         let p2 = points[points.length - 1]
 10 | 
 11 |         for (let i = points.length - 1; i > 0; i--) {
 12 |             if (points[i].x !== points[i - 1].x || points[i].y !== points[i - 1].y) {
 13 |                 p2 = points[i]
 14 |                 p1 = points[i - 1]
 15 |                 break
 16 |             }
 17 |         }
 18 | 
 19 |         const dx = p2.x - p1.x
 20 |         const dy = p2.y - p1.y
 21 | 
 22 |         let dir = 'down'
 23 |         if (Math.abs(dx) >= Math.abs(dy)) {
 24 |             dir = dx > 0 ? 'right' : 'left'
 25 |         } else {
 26 |             dir = dy > 0 ? 'down' : 'up'
 27 |         }
 28 |         return dir
 29 |     }
 30 | 
 31 |     const computedEdges = computed(() => {
 32 |         let edges = []
 33 |         const allNodes = renderNodes.value
 34 |         const activeDraggingId = draggingNodeId.value
 35 |         const isActuallyMoving = hasMoved.value
 36 | 
 37 |         allNodes.forEach(node => {
 38 |             if (node.on_success?.target_node) {
 39 |                 const target = allNodes.find(n => n.node_id === node.on_success.target_node)
 40 |                 if (target) {
 41 |                     let smoothPathStr = ''
 42 |                     let arrowDir = 'down'
 43 |                     let routeResult = null
 44 | 
 45 |                     const isThisEdgeDragging = activeDraggingId && isActuallyMoving && (node.node_id === activeDraggingId || target.node_id === activeDraggingId)
 46 | 
 47 |                     if (isThisEdgeDragging) {
 48 |                         const startPt = { x: node.position.x + node.w / 2, y: node.position.y + node.h }
 49 |                         const endPt = { x: target.position.x + target.w / 2, y: target.position.y }
 50 |                         const simplePoints = [startPt, { x: startPt.x, y: (startPt.y + endPt.y) / 2 }, { x: endPt.x, y: (startPt.y + endPt.y) / 2 }, endPt]
 51 |                         smoothPathStr = getRoundedPathString(simplePoints, 10)
 52 |                         arrowDir = getArrowDirection(simplePoints)
 53 |                         routeResult = { startPt, endPt }
 54 |                     } else {
 55 |                         const rr = router.route(node, target, allNodes, 'succ', true)
 56 |                         routeResult = rr
 57 |                         smoothPathStr = getRoundedPathString(rr.rawPixelPoints, 10)
 58 |                         arrowDir = getArrowDirection(rr.rawPixelPoints)
 59 |                     }
 60 | 
 61 |                     const edgeId = `e_${node.node_id}_succ_${target.node_id}`
 62 |                     edges.push({
 63 |                         id: edgeId,
 64 |                         sourceNodeId: node.node_id,
 65 |                         targetNodeId: target.node_id,
 66 |                         typeFlag: 'succ',
 67 |                         path: smoothPathStr,
 68 |                         isFail: false,
 69 |                         markerUrl: `url(#arrow-succ-${arrowDir})`,
 70 |                         selected: selectedEdgeId.value === edgeId,
 71 |                         labelX: (routeResult.startPt.x + routeResult.endPt.x) / 2,
 72 |                         labelY: (routeResult.startPt.y + routeResult.endPt.y) / 2 - 10,
 73 |                         rawPixelPoints: routeResult.rawPixelPoints || []
 74 |                     })
 75 |                 }
 76 |             }
 77 | 
 78 |             if (node.on_failure?.target_node) {
 79 |                 const target = allNodes.find(n => n.node_id === node.on_failure.target_node)
 80 |                 if (target) {
 81 |                     let smoothPathStr = ''
 82 |                     let arrowDir = 'down'
 83 |                     let routeResult = null
 84 | 
 85 |                     const isThisEdgeDragging = activeDraggingId && isActuallyMoving && (node.node_id === activeDraggingId || target.node_id === activeDraggingId)
 86 | 
 87 |                     if (isThisEdgeDragging) {
 88 |                         const startPt = { x: node.position.x + node.w, y: node.position.y + node.h / 2 }
 89 |                         const endPt = { x: target.position.x, y: target.position.y + target.h / 2 }
 90 |                         const simplePoints = [startPt, { x: (startPt.x + endPt.x) / 2, y: startPt.y }, { x: (startPt.x + endPt.x) / 2, y: endPt.y }, endPt]
 91 |                         smoothPathStr = getRoundedPathString(simplePoints, 10)
 92 |                         arrowDir = getArrowDirection(simplePoints)
 93 |                         routeResult = { startPt, endPt }
 94 |                     } else {
 95 |                         const rr = router.route(node, target, allNodes, 'fail')
 96 |                         routeResult = rr
 97 |                         smoothPathStr = getRoundedPathString(rr.rawPixelPoints, 10)
 98 |                         arrowDir = getArrowDirection(rr.rawPixelPoints)
 99 |                     }
100 | 
101 |                     const edgeId = `e_${node.node_id}_fail_${target.node_id}`
102 |                     edges.push({
103 |                         id: edgeId,
104 |                         sourceNodeId: node.node_id,
105 |                         targetNodeId: target.node_id,
106 |                         typeFlag: 'fail',
107 |                         path: smoothPathStr,
108 |                         isFail: true,
109 |                         markerUrl: `url(#arrow-fail-${arrowDir})`,
110 |                         selected: selectedEdgeId.value === edgeId,
111 |                         labelX: (routeResult.startPt.x + routeResult.endPt.x) / 2,
112 |                         labelY: (routeResult.startPt.y + routeResult.endPt.y) / 2 - 10,
113 |                         rawPixelPoints: routeResult.rawPixelPoints || []
114 |                     })
115 |                 }
116 |             }
117 |         })
118 | 
119 |         if (drawingConnection.value.active) {
120 |             const sourceNode = allNodes.find(n => n.node_id === drawingConnection.value.sourceNodeId)
121 |             if (sourceNode) {
122 |                 const startPt = drawingConnection.value.portType === 'succ'
123 |                     ? { x: sourceNode.position.x + sourceNode.w / 2, y: sourceNode.position.y + sourceNode.h }
124 |                     : { x: sourceNode.position.x + sourceNode.w, y: sourceNode.position.y + sourceNode.h / 2 }
125 | 
126 |                 const mousePt = { x: drawingConnection.value.currentX, y: drawingConnection.value.currentY }
127 | 
128 |                 let safeStartY = startPt.y
129 |                 if (drawingConnection.value.portType === 'succ') {
130 |                     safeStartY = Math.max(startPt.y + 20, mousePt.y)
131 |                 }
132 | 
133 |                 const rawPoints = [
134 |                     startPt,
135 |                     { x: startPt.x, y: safeStartY },
136 |                     { x: mousePt.x, y: safeStartY },
137 |                     mousePt
138 |                 ]
139 | 
140 |                 const pathStr = getRoundedPathString(rawPoints, 10)
141 |                 const arrowDir = getArrowDirection(rawPoints)
142 |                 drawingConnection.value.previewMarkerUrl = `url(#arrow-${drawingConnection.value.portType === 'fail' ? 'fail' : 'succ'}-${arrowDir})`
143 | 
144 |                 edges.push({
145 |                     id: 'temp_drawing',
146 |                     path: pathStr,
147 |                     label: '',
148 |                     isFail: drawingConnection.value.portType === 'fail',
149 |                     markerUrl: drawingConnection.value.previewMarkerUrl,
150 |                     selected: false,
151 |                     labelX: 0,
152 |                     labelY: 0,
153 |                     gridPoints: [],
154 |                     rawPixelPoints: rawPoints
155 |                 })
156 |             }
157 |         }
158 | 
159 |         return edges
160 |     })
161 | 
162 |     return {
163 |         computedEdges
164 |     }
165 | }
```

## File: D:\PycharmProjects\Easycode\frontend\src\composables\useCanvasViewport.js

- Extension: .js
- Language: javascript
- Size: 1418 bytes
- Created: 2026-08-06 10:32:53
- Modified: 2026-08-06 10:33:18

### Code

```javascript
 1 | import { ref, computed } from 'vue'
 2 | 
 3 | export function useCanvasViewport(containerRef) {
 4 |     const viewport = ref({ x: 0, y: 0, zoom: 1 })
 5 |     const isPanning = ref(false)
 6 |     const panStart = ref({ x: 0, y: 0 })
 7 | 
 8 |     const viewportStyle = computed(() => ({
 9 |         transform: `translate(${viewport.value.x}px, ${viewport.value.y}px) scale(${viewport.value.zoom})`,
10 |         transformOrigin: '0 0'
11 |     }))
12 | 
13 |     const handleCanvasWheel = (e, drawMinimap) => {
14 |         e.preventDefault()
15 |         if (!containerRef.value) return
16 | 
17 |         const rect = containerRef.value.getBoundingClientRect()
18 |         const mouseX = e.clientX - rect.left
19 |         const mouseY = e.clientY - rect.top
20 | 
21 |         const oldZoom = viewport.value.zoom
22 |         const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9
23 |         const newZoom = Math.min(Math.max(oldZoom * zoomFactor, 0.2), 4)
24 | 
25 |         if (newZoom === oldZoom) return
26 | 
27 |         const worldX = (mouseX - viewport.value.x) / oldZoom
28 |         const worldY = (mouseY - viewport.value.y) / oldZoom
29 | 
30 |         viewport.value.zoom = newZoom
31 |         viewport.value.x = mouseX - worldX * newZoom
32 |         viewport.value.y = mouseY - worldY * newZoom
33 | 
34 |         if (typeof drawMinimap === 'function') {
35 |             drawMinimap()
36 |         }
37 |     }
38 | 
39 |     return {
40 |         viewport,
41 |         isPanning,
42 |         panStart,
43 |         viewportStyle,
44 |         handleCanvasWheel
45 |     }
46 | }
```

## File: D:\PycharmProjects\Easycode\frontend\src\config\panelsConfig.js

- Extension: .js
- Language: javascript
- Size: 1310 bytes
- Created: 2026-08-10 12:09:04
- Modified: 2026-08-10 14:33:20

### Code

```javascript
 1 | // frontend/src/config/panelsConfig.js
 2 | import { defineAsyncComponent } from 'vue'
 3 | import { FolderTree, Binary, Puzzle, Sliders, Terminal } from 'lucide-vue-next'
 4 | 
 5 | export const leftPanelsConfig = [
 6 |     {
 7 |         id: 'explorer',
 8 |         title: '项目资源管理器',
 9 |         icon: FolderTree,
10 |         component: defineAsyncComponent(() => import('@/components/panels/ProjectExplorerPanel.vue'))
11 |     },
12 |     {
13 |         id: 'variables',
14 |         title: '全局变量监控',
15 |         icon: Binary,
16 |         component: defineAsyncComponent(() => import('@/components/panels/GlobalVariablesPanel.vue'))
17 |     },
18 |     {
19 |         id: 'plugins',
20 |         title: '扩展插件中心',
21 |         icon: Puzzle,
22 |         component: defineAsyncComponent(() => import('@/components/panels/PluginMarketPanel.vue'))
23 |     }
24 | ]
25 | 
26 | export const rightPanelsConfig = [
27 |     {
28 |         id: 'inspector',
29 |         title: '节点属性检查器',
30 |         icon: Sliders,
31 |         component: defineAsyncComponent(() => import('@/components/inspector/WorkflowInspector.vue'))
32 |     }
33 | ]
34 | 
35 | export const bottomPanelsConfig = [
36 |     {
37 |         id: 'console',
38 |         title: '运行控制台日志',
39 |         icon: Terminal,
40 |         component: defineAsyncComponent(() => import('@/components/canvas/CanvasLogPanel.vue'))
41 |     }
42 | ]
```

## File: D:\PycharmProjects\Easycode\frontend\src\layouts\IdeLayout.vue

- Extension: .vue
- Language: unknown
- Size: 14738 bytes
- Created: 2026-08-10 11:15:31
- Modified: 2026-08-10 17:35:26

### Code

```unknown
  1 | ﻿<!-- frontend/src/layouts/IdeLayout.vue -->
  2 | <template>
  3 |     <div class="ide-shell-layout">
  4 |         <!-- 1. 顶部主菜单栏 -->
  5 |         <TopMenuBar @run="handleRun" @openSettings="settingsVisible = true" />
  6 | 
  7 |         <!-- 2. 全局主工作区 -->
  8 |         <div class="ide-workspace-root">
  9 | 
 10 |             <!-- 左侧固定 40px 图标栏 -->
 11 |             <div class="fixed-dock-left">
 12 |                 <ActivityBar position="left"
 13 |                              :items="leftPanelsConfig"
 14 |                              :active-id="leftActive"
 15 |                              @select="toggleLeftPanel" />
 16 |                 <div class="bottom-toggle-dock">
 17 |                     <el-tooltip v-for="item in bottomPanelsConfig"
 18 |                                 :key="item.id"
 19 |                                 effect="dark"
 20 |                                 :content="item.title"
 21 |                                 placement="right"
 22 |                                 :show-after="300"
 23 |                                 popper-class="ide-sidebar-tooltip">
 24 |                         <div class="activity-icon-item"
 25 |                              :class="{ 'is-active': store.uiState.bottomPanelExpanded && bottomActive === item.id }"
 26 |                              @click="toggleBottomPanel(item.id)">
 27 |                             <component :is="item.icon" class="act-svg" />
 28 |                         </div>
 29 |                     </el-tooltip>
 30 |                 </div>
 31 |             </div>
 32 | 
 33 |             <!-- 中间大区域 -->
 34 |             <div class="ide-middle-area">
 35 | 
 36 |                 <!-- 上半行：左侧面板 + 画布 + 右侧面板 -->
 37 |                 <div class="ide-upper-row">
 38 |                     <!-- 左侧展开面板 -->
 39 |                     <ToolWindow v-if="store.uiState.leftPanelExpanded && currentLeftPanel"
 40 |                                 :title="currentLeftPanel.title"
 41 |                                 :width="store.uiState.leftPanelWidth + 'px'"
 42 |                                 class="ide-card-panel"
 43 |                                 @close="store.updateUiState('leftPanelExpanded', false)">
 44 |                         <component :is="currentLeftPanel.component" />
 45 |                     </ToolWindow>
 46 | 
 47 |                     <!-- 左侧 5px 拖拽调节分割线 -->
 48 |                     <div v-if="store.uiState.leftPanelExpanded && currentLeftPanel"
 49 |                          class="splitter-v"
 50 |                          @mousedown="startLeftResize" />
 51 | 
 52 |                     <!-- 中央画布区域 -->
 53 |                     <div class="ide-center-viewport ide-card-panel">
 54 |                         <div class="pane-content-inner">
 55 |                             <WorkflowCanvas />
 56 |                         </div>
 57 |                     </div>
 58 | 
 59 |                     <!-- 右侧 5px 拖拽调节分割线 -->
 60 |                     <div v-if="store.uiState.rightPanelExpanded && currentRightPanel"
 61 |                          class="splitter-v"
 62 |                          @mousedown="startRightResize" />
 63 | 
 64 |                     <!-- 右侧展开面板 -->
 65 |                     <ToolWindow v-if="store.uiState.rightPanelExpanded && currentRightPanel"
 66 |                                 :title="currentRightPanel.title"
 67 |                                 :width="store.uiState.rightPanelWidth + 'px'"
 68 |                                 class="ide-card-panel"
 69 |                                 @close="store.updateUiState('rightPanelExpanded', false)">
 70 |                         <component :is="currentRightPanel.component" />
 71 |                     </ToolWindow>
 72 |                 </div>
 73 | 
 74 |                 <!-- 底部 5px 拖拽调节分割线 -->
 75 |                 <div v-if="store.uiState.bottomPanelExpanded && currentBottomPanel"
 76 |                      class="splitter-h"
 77 |                      @mousedown="startBottomResize" />
 78 | 
 79 |                 <!-- 下半行：底部工具窗口 -->
 80 |                 <ToolWindow v-if="store.uiState.bottomPanelExpanded && currentBottomPanel"
 81 |                             :title="currentBottomPanel.title"
 82 |                             width="100%"
 83 |                             :height="store.uiState.bottomPanelHeight + 'px'"
 84 |                             class="ide-card-panel"
 85 |                             @close="store.updateUiState('bottomPanelExpanded', false)">
 86 |                     <component :is="currentBottomPanel.component" />
 87 |                 </ToolWindow>
 88 | 
 89 |             </div>
 90 | 
 91 |             <!-- 右侧固定 40px 图标栏 -->
 92 |             <div class="fixed-dock-right">
 93 |                 <ActivityBar position="right"
 94 |                              :items="rightPanelsConfig"
 95 |                              :active-id="rightActive"
 96 |                              @select="toggleRightPanel" />
 97 |             </div>
 98 | 
 99 |         </div>
100 | 
101 |         <!-- 3. 底部纯净状态栏 -->
102 |         <footer class="ide-status-footer">
103 |             <div class="status-left">
104 |                 <span class="status-dot">●</span>
105 |                 <span>就绪</span>
106 |                 <span class="status-divider">|</span>
107 |                 <span>项目路径: {{ store.currentProjectPath || '未打开' }}</span>
108 |             </div>
109 |             <div class="status-right">
110 |                 <span>执行状态: 空闲</span>
111 |                 <span class="status-divider">|</span>
112 |                 <span>UTF-8</span>
113 |                 <span class="status-divider">|</span>
114 |                 <span>Vue 3.5</span>
115 |             </div>
116 |         </footer>
117 | 
118 |         <!-- 面板设置弹窗 -->
119 |         <PanelSettingsDialog v-model:visible="settingsVisible" @apply="handleApplyContext" />
120 |     </div>
121 | </template>
122 | 
123 | <script setup>
124 |     import { ref, computed } from 'vue'
125 |     import { useMainStore } from '@/stores'
126 |     import { ElMessage } from 'element-plus'
127 | 
128 |     import TopMenuBar from '@/components/shell/TopMenuBar.vue'
129 |     import ActivityBar from '@/components/shell/ActivityBar.vue'
130 |     import ToolWindow from '@/components/shell/ToolWindow.vue'
131 |     import WorkflowCanvas from '@/components/WorkflowCanvas.vue'
132 |     import PanelSettingsDialog from '@/components/PanelSettingsDialog.vue'
133 | 
134 |     import { leftPanelsConfig, rightPanelsConfig, bottomPanelsConfig } from '@/config/panelsConfig'
135 | 
136 |     const store = useMainStore()
137 |     const settingsVisible = ref(false)
138 | 
139 |     // 左侧面板选项与切换（状态联动 store.uiState）
140 |     const leftActive = ref('explorer')
141 |     const currentLeftPanel = computed(() => leftPanelsConfig.find(p => p.id === leftActive.value))
142 | 
143 |     const toggleLeftPanel = (id) => {
144 |         if (leftActive.value === id && store.uiState.leftPanelExpanded) {
145 |             store.updateUiState('leftPanelExpanded', false)
146 |         } else {
147 |             leftActive.value = id
148 |             store.updateUiState('leftPanelExpanded', true)
149 |         }
150 |     }
151 | 
152 |     // 右侧面板选项与切换（状态联动 store.uiState）
153 |     const rightActive = ref('inspector')
154 |     const currentRightPanel = computed(() => rightPanelsConfig.find(p => p.id === rightActive.value))
155 | 
156 |     const toggleRightPanel = (id) => {
157 |         if (rightActive.value === id && store.uiState.rightPanelExpanded) {
158 |             store.updateUiState('rightPanelExpanded', false)
159 |         } else {
160 |             rightActive.value = id
161 |             store.updateUiState('rightPanelExpanded', true)
162 |         }
163 |     }
164 | 
165 |     // 底部面板选项与切换（状态联动 store.uiState）
166 |     const bottomActive = ref('console')
167 |     const currentBottomPanel = computed(() => bottomPanelsConfig.find(p => p.id === bottomActive.value))
168 | 
169 |     const toggleBottomPanel = (id) => {
170 |         if (bottomActive.value === id && store.uiState.bottomPanelExpanded) {
171 |             store.updateUiState('bottomPanelExpanded', false)
172 |         } else {
173 |             bottomActive.value = id
174 |             store.updateUiState('bottomPanelExpanded', true)
175 |         }
176 |     }
177 | 
178 |     // ⚡ 左侧面板拖拽调整宽度（实时保存到 JSON）
179 |     const startLeftResize = (e) => {
180 |         e.preventDefault()
181 |         const startX = e.clientX
182 |         const startW = store.uiState.leftPanelWidth
183 |         const onMouseMove = (moveEvent) => {
184 |             const dx = moveEvent.clientX - startX
185 |             const newW = Math.max(160, Math.min(startW + dx, 600))
186 |             store.updateUiState('leftPanelWidth', newW)
187 |         }
188 |         const onMouseUp = () => {
189 |             window.removeEventListener('mousemove', onMouseMove)
190 |             window.removeEventListener('mouseup', onMouseUp)
191 |         }
192 |         window.addEventListener('mousemove', onMouseMove)
193 |         window.addEventListener('mouseup', onMouseUp)
194 |     }
195 | 
196 |     // ⚡ 右侧面板拖拽调整宽度（实时保存到 JSON）
197 |     const startRightResize = (e) => {
198 |         e.preventDefault()
199 |         const startX = e.clientX
200 |         const startW = store.uiState.rightPanelWidth
201 |         const onMouseMove = (moveEvent) => {
202 |             const dx = startX - moveEvent.clientX
203 |             const newW = Math.max(200, Math.min(startW + dx, 600))
204 |             store.updateUiState('rightPanelWidth', newW)
205 |         }
206 |         const onMouseUp = () => {
207 |             window.removeEventListener('mousemove', onMouseMove)
208 |             window.removeEventListener('mouseup', onMouseUp)
209 |         }
210 |         window.addEventListener('mousemove', onMouseMove)
211 |         window.addEventListener('mouseup', onMouseUp)
212 |     }
213 | 
214 |     // ⚡ 底部面板拖拽调整高度（实时保存到 JSON）
215 |     const startBottomResize = (e) => {
216 |         e.preventDefault()
217 |         const startY = e.clientY
218 |         const startH = store.uiState.bottomPanelHeight
219 |         const onMouseMove = (moveEvent) => {
220 |             const dy = startY - moveEvent.clientY
221 |             const newH = Math.max(80, Math.min(startH + dy, 500))
222 |             store.updateUiState('bottomPanelHeight', newH)
223 |         }
224 |         const onMouseUp = () => {
225 |             window.removeEventListener('mousemove', onMouseMove)
226 |             window.removeEventListener('mouseup', onMouseUp)
227 |         }
228 |         window.addEventListener('mousemove', onMouseMove)
229 |         window.addEventListener('mouseup', onMouseUp)
230 |     }
231 | 
232 |     const handleRun = async () => {
233 |         if (!store.currentTaskId) return ElMessage.warning('请先选择任务')
234 |         await store.runTask(store.currentTaskId, null)
235 |         ElMessage.success('任务已启动')
236 |     }
237 | 
238 |     const handleApplyContext = async (ctx) => {
239 |         await store.setCurrentContext(ctx)
240 |         ElMessage.success('工作面板切换成功')
241 |     }
242 | </script>
243 | 
244 | <style scoped>
245 |     .ide-shell-layout {
246 |         width: 100vw;
247 |         height: 100vh;
248 |         display: flex;
249 |         flex-direction: column;
250 |         background: #12131e;
251 |         overflow: hidden;
252 |         box-sizing: border-box;
253 |     }
254 | 
255 |     .ide-workspace-root {
256 |         flex: 1;
257 |         display: flex;
258 |         position: relative;
259 |         overflow: hidden;
260 |         background: #12131e;
261 |     }
262 | 
263 |     .fixed-dock-left, .fixed-dock-right {
264 |         width: 40px;
265 |         height: 100%;
266 |         background: #181926;
267 |         flex-shrink: 0;
268 |         z-index: 60;
269 |         user-select: none;
270 |         display: flex;
271 |         flex-direction: column;
272 |     }
273 | 
274 |     .fixed-dock-left {
275 |         border-right: 1px solid rgba(255, 255, 255, 0.05);
276 |     }
277 | 
278 |     .fixed-dock-right {
279 |         border-left: 1px solid rgba(255, 255, 255, 0.05);
280 |     }
281 | 
282 |     .fixed-dock-left :deep(.activity-bar) {
283 |         flex: 1;
284 |         border-right: none !important;
285 |         width: 100%;
286 |     }
287 | 
288 |     .bottom-toggle-dock {
289 |         flex-shrink: 0;
290 |         padding-bottom: 8px;
291 |         display: flex;
292 |         flex-direction: column;
293 |         align-items: center;
294 |         gap: 4px;
295 |         border-top: 1px solid rgba(255, 255, 255, 0.05);
296 |         padding-top: 8px;
297 |     }
298 | 
299 |     .activity-icon-item {
300 |         width: 32px;
301 |         height: 32px;
302 |         border-radius: 6px;
303 |         display: flex;
304 |         align-items: center;
305 |         justify-content: center;
306 |         cursor: pointer;
307 |         color: var(--el-text-color-secondary);
308 |         transition: all 0.2s ease;
309 |     }
310 | 
311 |         .activity-icon-item:hover {
312 |             background: var(--el-fill-color-light);
313 |             color: var(--el-text-color-primary);
314 |         }
315 | 
316 |         .activity-icon-item.is-active {
317 |             background: rgba(78, 209, 156, 0.15);
318 |             color: var(--el-color-primary);
319 |         }
320 | 
321 |     .act-svg {
322 |         width: 18px;
323 |         height: 18px;
324 |     }
325 | 
326 |     .ide-middle-area {
327 |         flex: 1;
328 |         display: flex;
329 |         flex-direction: column;
330 |         position: relative;
331 |         overflow: hidden;
332 |         padding: 4px;
333 |         box-sizing: border-box;
334 |     }
335 | 
336 |     .ide-upper-row {
337 |         flex: 1;
338 |         display: flex;
339 |         position: relative;
340 |         overflow: hidden;
341 |     }
342 | 
343 |     .ide-center-viewport {
344 |         flex: 1;
345 |         display: flex;
346 |         flex-direction: column;
347 |         position: relative;
348 |         overflow: hidden;
349 |         background: #2b2d3d;
350 |     }
351 | 
352 |     .pane-content-inner {
353 |         flex: 1;
354 |         position: relative;
355 |         overflow: hidden;
356 |     }
357 | 
358 |     .ide-card-panel {
359 |         border-radius: 8px !important;
360 |         overflow: hidden !important;
361 |         box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
362 |         border: 1px solid rgba(255, 255, 255, 0.06) !important;
363 |     }
364 | 
365 |     .splitter-v {
366 |         width: 5px;
367 |         height: 100%;
368 |         cursor: col-resize;
369 |         flex-shrink: 0;
370 |         background: transparent;
371 |         transition: background 0.2s ease;
372 |         z-index: 10;
373 |     }
374 | 
375 |         .splitter-v:hover {
376 |             background: var(--el-color-primary);
377 |         }
378 | 
379 |     .splitter-h {
380 |         width: 100%;
381 |         height: 5px;
382 |         cursor: row-resize;
383 |         flex-shrink: 0;
384 |         background: transparent;
385 |         transition: background 0.2s ease;
386 |         z-index: 10;
387 |     }
388 | 
389 |         .splitter-h:hover {
390 |             background: var(--el-color-primary);
391 |         }
392 | 
393 |     .ide-status-footer {
394 |         height: 26px;
395 |         background: #181926;
396 |         border-top: 1px solid var(--el-border-color-light);
397 |         display: flex;
398 |         align-items: center;
399 |         justify-content: space-between;
400 |         padding: 0 12px;
401 |         font-size: 11px;
402 |         color: var(--el-text-color-secondary);
403 |         flex-shrink: 0;
404 |         user-select: none;
405 |         z-index: 1000;
406 |     }
407 | 
408 |     .status-left, .status-right {
409 |         display: flex;
410 |         align-items: center;
411 |         gap: 8px;
412 |     }
413 | 
414 |     .status-dot {
415 |         color: var(--el-color-primary);
416 |         font-size: 10px;
417 |     }
418 | 
419 |     .status-divider {
420 |         color: var(--el-border-color-light);
421 |     }
422 | </style>
```

## File: D:\PycharmProjects\Easycode\frontend\src\stores\index.js

- Extension: .js
- Language: javascript
- Size: 10901 bytes
- Created: 2026-07-31 13:34:12
- Modified: 2026-08-10 17:57:55

### Code

```javascript
  1 | // frontend/src/stores/index.js
  2 | import { defineStore } from 'pinia'
  3 | import { blueprintApi } from '@/api/blueprintApi'
  4 | import { workspaceApi } from '@/api/workspaceApi'
  5 | import { logger } from '@/utils/logger'
  6 | import debounce from 'lodash-es/debounce'
  7 | 
  8 | // 默认 UI 布局配置
  9 | const DEFAULT_UI_STATE = {
 10 |     leftPanelExpanded: true,
 11 |     leftPanelWidth: 260,
 12 |     rightPanelExpanded: true,
 13 |     rightPanelWidth: 320,
 14 |     bottomPanelExpanded: true,
 15 |     bottomPanelHeight: 200,
 16 |     minimapExpanded: true
 17 | }
 18 | 
 19 | export const useMainStore = defineStore('main', {
 20 |     state: () => ({
 21 |         currentProjectPath: localStorage.getItem('lastProjectPath') || null,
 22 |         currentProjectName: '',
 23 |         blueprint: {
 24 |             project_name: '',
 25 |             tasks: [],
 26 |             variables: {},
 27 |             ui_state: { ...DEFAULT_UI_STATE } // ⚡ 存在项目 JSON 里的 UI 界面布局数据
 28 |         },
 29 |         paramsDefinitions: {},
 30 |         currentTaskId: null,
 31 |         selectedNodeId: null,
 32 |         recentProjects: JSON.parse(localStorage.getItem('recentProjects') || '[]'),
 33 |         currentContext: {
 34 |             workMode: 'window',
 35 |             windowTitle: '',
 36 |             isEmulator: false,
 37 |             offsetTop: 0,
 38 |             offsetBottom: 0,
 39 |             offsetLeft: 0,
 40 |             offsetRight: 0,
 41 |             targetContentWidth: 0,
 42 |             targetContentHeight: 0
 43 |         },
 44 |         executionLogs: [],
 45 |         taskNodesVersion: 0,
 46 | 
 47 |         selectedNodeIds: [],
 48 |         selectedGroupId: null,
 49 |         activeEventSource: null
 50 |     }),
 51 | 
 52 |     getters: {
 53 |         tasks: (state) => state.blueprint.tasks || [],
 54 |         currentTaskData: (state) => state.blueprint,
 55 |         currentTask: (state) => (state.blueprint.tasks || []).find(t => t.task_id === state.currentTaskId),
 56 |         nodes: (state) => {
 57 |             const task = (state.blueprint.tasks || []).find(t => t.task_id === state.currentTaskId)
 58 |             return task ? task.nodes || [] : []
 59 |         },
 60 |         selectedNode: (state) => {
 61 |             for (const task of (state.blueprint.tasks || [])) {
 62 |                 const node = (task.nodes || []).find(n => n.node_id === state.selectedNodeId)
 63 |                 if (node) return node
 64 |             }
 65 |             return null
 66 |         },
 67 |         params: (state) => state.paramsDefinitions,
 68 | 
 69 |         // ⚡ 快捷获取 UI 布局状态（防止字段为空，提供兜底默认值）
 70 |         uiState: (state) => ({
 71 |             ...DEFAULT_UI_STATE,
 72 |             ...(state.blueprint?.ui_state || {})
 73 |         })
 74 |     },
 75 | 
 76 |     actions: {
 77 |         async loadParams() {
 78 |             try {
 79 |                 this.paramsDefinitions = await blueprintApi.getParams()
 80 |             } catch (err) {
 81 |                 console.error('加载节点参数定义失败', err)
 82 |             }
 83 |         },
 84 | 
 85 |         async loadProjectByPath(path) {
 86 |             if (!path) return
 87 |             await blueprintApi.verifyProject(path)
 88 |             this.currentProjectPath = path
 89 |             this.currentProjectName = path.split(/[\\/]/).pop() || path
 90 |             localStorage.setItem('lastProjectPath', path)
 91 | 
 92 |             const existing = this.recentProjects.filter(p => p.path !== path)
 93 |             this.recentProjects = [{ name: this.currentProjectName, path }, ...existing].slice(0, 5)
 94 |             localStorage.setItem('recentProjects', JSON.stringify(this.recentProjects))
 95 | 
 96 |             await this.loadProjectData()
 97 |             await this.loadContext()
 98 |         },
 99 | 
100 |         async loadProjectData() {
101 |             if (!this.currentProjectPath) return
102 |             const data = await blueprintApi.getBlueprint(this.currentProjectPath)
103 | 
104 |             // ⚡ 读取保存的 ui_state，若为空则补充默认值
105 |             if (!data.ui_state) {
106 |                 data.ui_state = { ...DEFAULT_UI_STATE }
107 |             } else {
108 |                 data.ui_state = { ...DEFAULT_UI_STATE, ...data.ui_state }
109 |             }
110 | 
111 |             this.blueprint = data
112 |             this.currentProjectName = data.project_name || this.currentProjectName
113 | 
114 |             if (data.tasks && data.tasks.length > 0) {
115 |                 if (!this.currentTaskId || !data.tasks.some(t => t.task_id === this.currentTaskId)) {
116 |                     this.currentTaskId = data.tasks[0].task_id
117 |                 }
118 |             } else {
119 |                 this.currentTaskId = null
120 |             }
121 |             this.taskNodesVersion++
122 |         },
123 | 
124 |         // ⚡ 统一修改并保存 UI 状态（支持单项或批量更新，自动防抖落盘）
125 |         updateUiState(keyOrObject, value) {
126 |             if (!this.blueprint.ui_state) {
127 |                 this.blueprint.ui_state = { ...DEFAULT_UI_STATE }
128 |             }
129 | 
130 |             if (typeof keyOrObject === 'object') {
131 |                 Object.assign(this.blueprint.ui_state, keyOrObject)
132 |             } else if (typeof keyOrObject === 'string') {
133 |                 this.blueprint.ui_state[keyOrObject] = value
134 |             }
135 | 
136 |             // 自动触发放抖落盘写入 project_blueprint.json
137 |             this.saveBlueprintDebounced()
138 |         },
139 | 
140 |         async loadTasks() {
141 |             await this.loadProjectData()
142 |             return this.tasks
143 |         },
144 | 
145 |         async loadContext() {
146 |             if (!this.currentProjectPath) return
147 |             try {
148 |                 const ctx = await workspaceApi.getContext(this.currentProjectPath)
149 |                 if (ctx) {
150 |                     this.currentContext = {
151 |                         workMode: ctx.windowTitle ? 'window' : 'desktop',
152 |                         ...ctx
153 |                     }
154 |                 }
155 |             } catch (err) {
156 |                 console.error('加载工作区上下文失败', err)
157 |             }
158 |         },
159 | 
160 |         async setCurrentContext(context) {
161 |             this.currentContext = { ...context }
162 |             if (this.currentProjectPath) {
163 |                 await workspaceApi.saveContext(this.currentProjectPath, context)
164 |             }
165 |         },
166 | 
167 |         saveBlueprintDebounced: debounce(async function () {
168 |             if (!this.currentProjectPath) return
169 |             try {
170 |                 await blueprintApi.saveBlueprint(this.currentProjectPath, this.blueprint)
171 |             } catch (err) {
172 |                 console.error('防抖保存蓝图失败', err)
173 |             }
174 |         }, 400),
175 | 
176 |         async saveBlueprintImmediately() {
177 |             if (!this.currentProjectPath) return
178 |             await blueprintApi.saveBlueprint(this.currentProjectPath, this.blueprint)
179 |         },
180 | 
181 |         async saveCurrentTask() {
182 |             await this.saveBlueprintImmediately()
183 |         },
184 | 
185 |         async loadTaskNodes(taskId) {
186 |             if (!this.currentProjectPath || !taskId) return []
187 |             return await blueprintApi.getTaskNodes(taskId, this.currentProjectPath)
188 |         },
189 | 
190 |         async createNewTask(taskName) {
191 |             if (!this.currentProjectPath) return
192 |             const res = await blueprintApi.createTask(this.currentProjectPath, { task_name: taskName, nodes: [] })
193 |             await this.loadProjectData()
194 |             return res
195 |         },
196 | 
197 |         async runTask(taskId, startNodeId) {
198 |             if (this.activeEventSource) {
199 |                 this.activeEventSource.close()
200 |                 this.activeEventSource = null
201 |             }
202 | 
203 |             this.executionLogs = []
204 |             // 运行任务时如果底部面板被收起了，自动展开
205 |             this.updateUiState('bottomPanelExpanded', true)
206 | 
207 |             logger.info('Store', `正在准备启动任务: ${taskId}`)
208 | 
209 |             try {
210 |                 const res = await blueprintApi.runTask(this.currentProjectPath, taskId, startNodeId, this.blueprint)
211 |                 const executionId = res.execution_id || res.data?.execution_id
212 | 
213 |                 if (!executionId) {
214 |                     logger.error('Store', '启动任务失败: 未获得 execution_id', res)
215 |                     this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: '❌ 任务启动失败: 未获得 execution_id' })
216 |                     return res
217 |                 }
218 | 
219 |                 this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: `🚀 任务 [${taskId}] 已启动...` })
220 | 
221 |                 const sseUrl = `/api/execution/${executionId}/stream`
222 |                 const eventSource = new EventSource(sseUrl)
223 |                 this.activeEventSource = eventSource
224 | 
225 |                 eventSource.onmessage = (event) => {
226 |                     try {
227 |                         const payload = JSON.parse(event.data)
228 |                         const newLogs = payload.logs || []
229 |                         const status = payload.status || {}
230 | 
231 |                         if (Array.isArray(newLogs) && newLogs.length > 0) {
232 |                             newLogs.forEach(logItem => {
233 |                                 const msg = typeof logItem === 'string' ? logItem : logItem.message
234 |                                 this.executionLogs.push(typeof logItem === 'string' ? { time: new Date().toLocaleTimeString(), message: logItem } : logItem)
235 |                                 logger.debug('SSE-Stream', msg)
236 |                             })
237 |                         }
238 | 
239 |                         if (status.status === 'success' || status.status === 'error') {
240 |                             logger.info('Store', `任务流程结束, 最终状态: ${status.status}`)
241 |                             this.executionLogs.push({
242 |                                 time: new Date().toLocaleTimeString(),
243 |                                 message: status.status === 'success' ? '🎉 任务流程执行完毕 ✅' : `💥 任务终止: ${status.message}`
244 |                             })
245 |                             eventSource.close()
246 |                             this.activeEventSource = null
247 |                         }
248 |                     } catch (e) {
249 |                         logger.error('Store', '解析 SSE 日志流数据失败', e)
250 |                     }
251 |                 }
252 | 
253 |                 eventSource.onerror = (err) => {
254 |                     logger.warn('Store', 'SSE 日志流连接已关闭或断开', err)
255 |                     eventSource.close()
256 |                     this.activeEventSource = null
257 |                 }
258 | 
259 |                 return res
260 |             } catch (err) {
261 |                 logger.error('Store', 'runTask 触发异常', err)
262 |                 this.executionLogs.push({ time: new Date().toLocaleTimeString(), message: `❌ 启动任务失败: ${err.message}` })
263 |                 throw err
264 |             }
265 |         },
266 | 
267 |         toggleMinimap() {
268 |             this.updateUiState('minimapExpanded', !this.uiState.minimapExpanded)
269 |         },
270 | 
271 |         toggleLogPanel() {
272 |             this.updateUiState('bottomPanelExpanded', !this.uiState.bottomPanelExpanded)
273 |         }
274 |     }
275 | })
```

## File: D:\PycharmProjects\Easycode\frontend\src\utils\gridRouter.js

- Extension: .js
- Language: javascript
- Size: 8288 bytes
- Created: 2026-08-04 22:00:11
- Modified: 2026-08-11 22:26:31

### Code

```javascript
  1 | ﻿// frontend/src/utils/gridRouter.js
  2 | import PF from 'pathfinding'
  3 | 
  4 | export class GridWorkflowRouter {
  5 |     constructor(gridSize = 20) {
  6 |         this.GRID_SIZE = gridSize
  7 |     }
  8 | 
  9 |     toGridCoord(pixelX, pixelY) {
 10 |         return {
 11 |             x: Math.round(pixelX / this.GRID_SIZE),
 12 |             y: Math.round(pixelY / this.GRID_SIZE)
 13 |         }
 14 |     }
 15 | 
 16 |     toPixelCoord(gridX, gridY) {
 17 |         return {
 18 |             x: gridX * this.GRID_SIZE,
 19 |             y: gridY * this.GRID_SIZE
 20 |         }
 21 |     }
 22 | 
 23 |     getNodeCornerGrids(node) {
 24 |         const w = node.w || 160
 25 |         const h = node.h || 80
 26 |         const x = node.position?.x || 0
 27 |         const y = node.position?.y || 0
 28 | 
 29 |         return {
 30 |             topLeft: this.toGridCoord(x, y),
 31 |             topRight: this.toGridCoord(x + w, y),
 32 |             bottomLeft: this.toGridCoord(x, y + h),
 33 |             bottomRight: this.toGridCoord(x + w, y + h)
 34 |         }
 35 |     }
 36 | 
 37 |     route(sourceNode, targetNode, allNodes = [], portType = 'succ', enableSimplify = true) {
 38 |         const sSize = { w: sourceNode.w || 160, h: sourceNode.h || 80 }
 39 |         const tSize = { w: targetNode.w || 160, h: targetNode.h || 80 }
 40 | 
 41 |         const mapWidth = 300
 42 |         const mapHeight = 300
 43 |         const gridCols = mapWidth
 44 |         const gridRows = mapHeight
 45 |         const gridOffsetX = 150
 46 |         const gridOffsetY = 150
 47 | 
 48 |         const grid = new PF.Grid(gridCols, gridRows)
 49 | 
 50 |         // 1. 节点建筑物设为不可通行
 51 |         allNodes.forEach(n => {
 52 |             const x = n.position?.x || 0
 53 |             const y = n.position?.y || 0
 54 |             const w = n.w || 160
 55 |             const h = n.h || 80
 56 | 
 57 |             const gStart = this.toGridCoord(x, y)
 58 |             const gEnd = this.toGridCoord(x + w, y + h)
 59 | 
 60 |             const minGX = Math.max(0, gStart.x + gridOffsetX)
 61 |             const maxGX = Math.min(gridCols - 1, gEnd.x + gridOffsetX)
 62 |             const minGY = Math.max(0, gStart.y + gridOffsetY)
 63 |             const maxGY = Math.min(gridRows - 1, gEnd.y + gridOffsetY)
 64 | 
 65 |             for (let gx = minGX; gx <= maxGX; gx++) {
 66 |                 for (let gy = minGY; gy <= maxGY; gy++) {
 67 |                     grid.setWalkableAt(gx, gy, false)
 68 |                 }
 69 |             }
 70 |         })
 71 | 
 72 |         // 2. ⚡ 精准计算不同端口类型的起止像素桩
 73 |         let startPixelPt = { x: 0, y: 0 }
 74 | 
 75 |         if (portType === 'succ') {
 76 |             startPixelPt = { x: sourceNode.position.x + sSize.w / 2, y: sourceNode.position.y + sSize.h }
 77 |         } else if (portType.startsWith('branch_')) {
 78 |             // ⚡ 核心修正：锁定 CSS 真实卡片高度与边距（卡片顶边距 8 + 头部 16 + 容器边距 4 + 列表边距 2 + 单项中心 12 = 42px，单项步长 28px）
 79 |             const cIdx = parseInt(portType.split('_')[1]) || 0
 80 |             const exactOffsetY = 42 + cIdx * 28
 81 |             startPixelPt = { x: sourceNode.position.x + sSize.w, y: sourceNode.position.y + exactOffsetY }
 82 |         } else {
 83 |             // ⚡ 核心修正：Branch 节点的 Else 兜底红点在右下方（bottom: 12px），中心 Y 轴为 h - 18px
 84 |             const isBranchNode = sourceNode.node_type === 'branch'
 85 |             const exactOffsetY = isBranchNode ? (sSize.h - 18) : (sSize.h / 2)
 86 |             startPixelPt = { x: sourceNode.position.x + sSize.w, y: sourceNode.position.y + exactOffsetY }
 87 |         }
 88 | 
 89 |         const endPixelPt = {
 90 |             x: targetNode.position.x + tSize.w / 2,
 91 |             y: targetNode.position.y
 92 |         }
 93 | 
 94 |         let stubStart = { ...startPixelPt }
 95 |         if (portType === 'succ') {
 96 |             stubStart.y += this.GRID_SIZE
 97 |         } else {
 98 |             // 所有右侧导出的端口，初始向右向外延伸一个网格
 99 |             stubStart.x += this.GRID_SIZE
100 |         }
101 | 
102 |         let stubEnd = {
103 |             x: endPixelPt.x,
104 |             y: endPixelPt.y - this.GRID_SIZE
105 |         }
106 | 
107 |         const makeWalkable = (pt) => {
108 |             const g = this.toGridCoord(pt.x, pt.y)
109 |             const gx = g.x + gridOffsetX
110 |             const gy = g.y + gridOffsetY
111 |             if (gx >= 0 && gx < gridCols && gy >= 0 && gy < gridRows) {
112 |                 grid.setWalkableAt(gx, gy, true)
113 |             }
114 |         }
115 |         makeWalkable(startPixelPt)
116 |         makeWalkable(stubStart)
117 |         makeWalkable(stubEnd)
118 |         makeWalkable(endPixelPt)
119 | 
120 |         const startG = this.toGridCoord(stubStart.x, stubStart.y)
121 |         const endG = this.toGridCoord(stubEnd.x, stubEnd.y)
122 | 
123 |         const sX = Math.min(Math.max(startG.x + gridOffsetX, 0), gridCols - 1)
124 |         const sY = Math.min(Math.max(startG.y + gridOffsetY, 0), gridRows - 1)
125 |         const eX = Math.min(Math.max(endG.x + gridOffsetX, 0), gridCols - 1)
126 |         const eY = Math.min(Math.max(endG.y + gridOffsetY, 0), gridRows - 1)
127 | 
128 |         const finder = new PF.AStarFinder({
129 |             allowDiagonal: false,
130 |             dontCrossCorners: true
131 |         })
132 | 
133 |         const path = finder.findPath(sX, sY, eX, eY, grid.clone())
134 |         let simplifiedPts = []
135 | 
136 |         if (path && path.length > 0) {
137 |             let rawPoints = path.map(p => this.toPixelCoord(p[0] - gridOffsetX, p[1] - gridOffsetY))
138 | 
139 |             rawPoints = [
140 |                 startPixelPt,
141 |                 stubStart,
142 |                 ...rawPoints,
143 |                 stubEnd,
144 |                 endPixelPt
145 |             ]
146 | 
147 |             let orthogonalPts = [rawPoints[0]]
148 |             for (let i = 1; i < rawPoints.length; i++) {
149 |                 const prev = orthogonalPts[orthogonalPts.length - 1]
150 |                 const curr = rawPoints[i]
151 | 
152 |                 if (prev.x !== curr.x && prev.y !== curr.y) {
153 |                     orthogonalPts.push({ x: curr.x, y: prev.y })
154 |                 }
155 |                 orthogonalPts.push(curr)
156 |             }
157 | 
158 |             simplifiedPts = [orthogonalPts[0]]
159 |             for (let i = 1; i < orthogonalPts.length - 1; i++) {
160 |                 const prev = simplifiedPts[simplifiedPts.length - 1]
161 |                 const curr = orthogonalPts[i]
162 |                 const next = orthogonalPts[i + 1]
163 |                 const isCollinear = (curr.x === prev.x && curr.x === next.x) || (curr.y === prev.y && curr.y === next.y)
164 |                 if (!isCollinear) {
165 |                     simplifiedPts.push(curr)
166 |                 }
167 |             }
168 |             simplifiedPts.push(orthogonalPts[orthogonalPts.length - 1])
169 | 
170 |         } else {
171 |             const midY = (startPixelPt.y + endPixelPt.y) / 2
172 |             simplifiedPts = [
173 |                 startPixelPt,
174 |                 stubStart,
175 |                 { x: stubStart.x, y: midY },
176 |                 { x: endPixelPt.x, y: midY },
177 |                 stubEnd,
178 |                 endPixelPt
179 |             ]
180 |         }
181 | 
182 |         const gridPoints = simplifiedPts.map(pt => this.toGridCoord(pt.x, pt.y))
183 |         const rawPixelPoints = simplifiedPts.map(pt => ({ x: pt.x, y: pt.y }))
184 | 
185 |         let pathStr = `M ${simplifiedPts[0].x} ${simplifiedPts[0].y}`
186 |         for (let i = 1; i < simplifiedPts.length; i++) {
187 |             pathStr += ` L ${simplifiedPts[i].x} ${simplifiedPts[i].y}`
188 |         }
189 | 
190 |         let arrowDir = 'down'
191 |         if (rawPixelPoints && rawPixelPoints.length >= 2) {
192 |             let p1 = rawPixelPoints[rawPixelPoints.length - 2]
193 |             let p2 = rawPixelPoints[rawPixelPoints.length - 1]
194 | 
195 |             for (let i = rawPixelPoints.length - 1; i > 0; i--) {
196 |                 if (rawPixelPoints[i].x !== rawPixelPoints[i - 1].x || rawPixelPoints[i].y !== rawPixelPoints[i - 1].y) {
197 |                     p2 = rawPixelPoints[i]
198 |                     p1 = rawPixelPoints[i - 1]
199 |                     break
200 |                 }
201 |             }
202 | 
203 |             const dx = p2.x - p1.x
204 |             const dy = p2.y - p1.y
205 | 
206 |             if (Math.abs(dx) >= Math.abs(dy)) {
207 |                 arrowDir = dx > 0 ? 'right' : 'left'
208 |             } else {
209 |                 arrowDir = dy > 0 ? 'down' : 'up'
210 |             }
211 |         }
212 | 
213 |         return {
214 |             startPt: simplifiedPts[0],
215 |             endPt: simplifiedPts[simplifiedPts.length - 1],
216 |             pathStr,
217 |             gridPoints,
218 |             rawPixelPoints,
219 |             arrowDir
220 |         }
221 |     }
222 | }
223 | 
224 | export const router = new GridWorkflowRouter(20)
```

## File: D:\PycharmProjects\Easycode\frontend\src\utils\logger.js

- Extension: .js
- Language: javascript
- Size: 1707 bytes
- Created: 2026-08-01 16:36:47
- Modified: 2026-08-01 16:38:47

### Code

```javascript
 1 | ﻿// frontend/src/utils/logger.js
 2 | 
 3 | // 日志级别：DEBUG(0) < INFO(1) < WARN(2) < ERROR(3)
 4 | const LEVELS = { DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3 };
 5 | 
 6 | // 默认开发环境为 DEBUG，可随时在浏览器控制台通过 window.__LOG_LEVEL__ = 'INFO' 修改
 7 | window.__LOG_LEVEL__ = process.env.NODE_ENV === 'development' ? 'DEBUG' : 'WARN';
 8 | 
 9 | function shouldLog(level) {
10 |     const currentLevel = LEVELS[window.__LOG_LEVEL__] ?? LEVELS.INFO;
11 |     return LEVELS[level] >= currentLevel;
12 | }
13 | 
14 | export const logger = {
15 |     debug(tag, ...args) {
16 |         if (shouldLog('DEBUG')) {
17 |             console.log(`🔍 [${tag}]`, ...args);
18 |         }
19 |     },
20 | 
21 |     info(tag, ...args) {
22 |         if (shouldLog('INFO')) {
23 |             console.log(`ℹ️ [${tag}]`, ...args);
24 |         }
25 |     },
26 | 
27 |     warn(tag, ...args) {
28 |         if (shouldLog('WARN')) {
29 |             console.warn(`⚠️ [${tag}]`, ...args);
30 |         }
31 |     },
32 | 
33 |     error(tag, ...args) {
34 |         if (shouldLog('ERROR')) {
35 |             console.error(`❌ [${tag}]`, ...args);
36 |         }
37 |     },
38 | 
39 |     // 展开式分组追踪（出 Bug 时看这个极度方便）
40 |     group(tag, title, callback) {
41 |         if (shouldLog('DEBUG')) {
42 |             console.group(`🚀 [${tag}] ${title}`);
43 |             try {
44 |                 callback();
45 |             } finally {
46 |                 console.groupEnd();
47 |             }
48 |         } else {
49 |             callback();
50 |         }
51 |     },
52 | 
53 |     // 追踪函数调用栈
54 |     trace(tag, msg) {
55 |         if (shouldLog('DEBUG')) {
56 |             console.groupCollapsed(`🕵️‍♂️ [${tag}] ${msg}`);
57 |             console.trace('调用栈轨迹');
58 |             console.groupEnd();
59 |         }
60 |     }
61 | };
```

