"""Build and exercise EasyCode first-party extension packages.

The packages are authored outside the destination project and always enter it
through the same signed import/trust/seal/enable lifecycle as third-party code.
Nothing in this module preinstalls an extension or bypasses the registry.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.vnext.bundle_signing_v6 import AuthorSigningKeyStore
from core.vnext.extension_schema_v6 import (
    ExtensionManifestV1,
    FunctionContractFileV1,
    MANIFEST_FILE,
    MANIFEST_SIGNATURE_FILE,
    sign_manifest,
)
from core.vnext.extensions import VNextExtensionRegistry
from core.vnext.runtime import RuntimeFailure
from core.vnext.workspace import VNextWorkspaceManager


PUBLISHER_ID = "com.easycode.firstparty"


@dataclass(frozen=True)
class PackageSpec:
    key: str
    package_id: str
    display_name: str
    description: str
    permissions: tuple[str, ...]
    network: dict[str, Any]
    contracts: tuple[dict[str, Any], ...]
    source: str
    readme: str


def _parameter(function_id: str, name: str, display_name: str, value_type: str = "string", *, required: bool = True, default: Any = None, control: str = "text") -> dict[str, Any]:
    value: dict[str, Any] = {
        "parameter_id": f"{function_id}.{name}", "name": name, "display_name": display_name,
        "value_type": value_type, "required": required, "control": {"control": control},
    }
    if not required:
        value["default"] = default
    return value


def function_contract(
    package_id: str,
    name: str,
    display: str,
    description: str,
    parameters: list[dict[str, Any]],
    *,
    result: str = "json",
    permissions: tuple[str, ...] = (),
    timeout: int = 30_000,
) -> dict[str, Any]:
    function_id = f"{package_id}.{name}"
    return {
        "function_id": function_id,
        "qualified_name": f"{display}",
        "description": description,
        "contract_version": "1.0.0",
        "parameters": parameters,
        "return_type": result,
        "targets": ["windows", "none"],
        "permissions": list(permissions),
        "timeout_ms": timeout,
        "contract_tests": [],
    }


BROWSER_SOURCE = r'''
"""Dependency-free Chromium DevTools Protocol client for the EasyCode browser package."""
import base64, hashlib, json, os, shutil, socket, ssl, struct, subprocess, tempfile, time, urllib.request

DEFAULT_PORT = 9222

def _http_json(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))
def _http_get(url):
    with urllib.request.urlopen(url, timeout=5) as response: return response.read().decode("utf-8")

def _endpoint(session):
    return str((session or {}).get("endpoint") or f"http://127.0.0.1:{DEFAULT_PORT}").rstrip("/")

def _target(session):
    rows = [row for row in _http_json(_endpoint(session) + "/json") if row.get("type") == "page"]
    wanted = str((session or {}).get("target_id") or "")
    return next((row for row in rows if row.get("id") == wanted), rows[0] if rows else None)

class CDP:
    def __init__(self, url):
        from urllib.parse import urlsplit
        value = urlsplit(url); host = value.hostname or "127.0.0.1"; port = value.port or 80
        self.sock = socket.create_connection((host, port), timeout=8)
        if value.scheme == "wss": self.sock = ssl.create_default_context().wrap_socket(self.sock, server_hostname=host)
        self.sock.settimeout(70)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (f"GET {value.path or '/'}?{value.query} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(request.encode("ascii")); response = b""
        while b"\r\n\r\n" not in response: response += self.sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]: raise RuntimeError("浏览器拒绝 DevTools WebSocket 连接")
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        if expected not in response: raise RuntimeError("DevTools WebSocket 握手校验失败")
        self.counter = 0
    def _read(self, size):
        data = b""
        while len(data) < size:
            part = self.sock.recv(size - len(data))
            if not part: raise RuntimeError("DevTools 连接已关闭")
            data += part
        return data
    def receive(self):
        head = self._read(2); length = head[1] & 127
        if length == 126: length = struct.unpack("!H", self._read(2))[0]
        elif length == 127: length = struct.unpack("!Q", self._read(8))[0]
        if head[1] & 128: mask = self._read(4)
        else: mask = None
        payload = self._read(length)
        if mask: payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        return json.loads(payload.decode("utf-8"))
    def call(self, method, params=None):
        self.counter += 1; request_id = self.counter
        payload = json.dumps({"id": request_id, "method": method, "params": params or {}}, ensure_ascii=False).encode("utf-8")
        mask = os.urandom(4); size = len(payload); header = bytes([0x81, 0x80 | size]) if size < 126 else bytes([0x81, 0x80 | 126]) + struct.pack("!H", size) if size < 65536 else bytes([0x81, 0x80 | 127]) + struct.pack("!Q", size)
        self.sock.sendall(header + mask + bytes(value ^ mask[index % 4] for index, value in enumerate(payload)))
        while True:
            response = self.receive()
            if response.get("id") == request_id:
                if "error" in response: raise RuntimeError(str(response["error"].get("message") or response["error"]))
                return response.get("result") or {}
    def close(self): self.sock.close()

def _session_for(endpoint, target): return {"endpoint": endpoint, "target_id": target.get("id", ""), "title": target.get("title", ""), "url": target.get("url", "")}
def _call(session, method, params=None):
    target = _target(session)
    if not target: raise RuntimeError("没有可用的浏览器标签页")
    client = CDP(target["webSocketDebuggerUrl"])
    try: return client.call(method, params)
    finally: client.close()
def _evaluate(session, expression, *, await_promise=False):
    result = _call(session, "Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": await_promise})
    if result.get("exceptionDetails"): raise RuntimeError("页面脚本执行失败")
    return (result.get("result") or {}).get("value")
def _element_expression(selector, body, frame_selector=""):
    selector_json = json.dumps(selector); frame_json = json.dumps(frame_selector)
    return f"""(() => {{ const f={frame_json}; const root=f ? document.querySelector(f)?.contentDocument : document; if(!root) throw new Error("iframe 不可访问"); const e=root.querySelector({selector_json}); if(!e) throw new Error("未找到元素"); {body} }})()"""

def launch_browser(context, browser, start_url):
    names = ["msedge.exe", "chrome.exe"] if str(browser).lower() != "chrome" else ["chrome.exe", "msedge.exe"]
    common = [os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"), os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"), os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")]
    executable = next((path for path in [*(shutil.which(name) for name in names), *common] if path and os.path.isfile(path)), None)
    if not executable: raise RuntimeError("未找到本机 Edge 或 Chrome")
    profile = tempfile.mkdtemp(prefix="EasyCodeBrowser-")
    subprocess.Popen([executable, f"--remote-debugging-port={DEFAULT_PORT}", f"--user-data-dir={profile}", "--no-first-run", str(start_url or "about:blank")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    endpoint = f"http://127.0.0.1:{DEFAULT_PORT}"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            target = _target({"endpoint": endpoint})
            if target: context.log("浏览器已连接"); return _session_for(endpoint, target)
        except Exception: pass
        time.sleep(.1)
    raise RuntimeError("浏览器启动后未开放 DevTools 连接")

def connect_browser(context, endpoint):
    endpoint = str(endpoint or f"http://127.0.0.1:{DEFAULT_PORT}").rstrip("/"); target = _target({"endpoint": endpoint})
    if not target: raise RuntimeError("该地址没有可用标签页")
    return _session_for(endpoint, target)
def open_url(context, session, url, wait_state):
    _call(session, "Page.enable"); _call(session, "Page.navigate", {"url": url});
    if wait_state != "none": wait_page(context, session, wait_state, 30000)
    return dict(session, url=url)
def go_back(context, session): _evaluate(session,"history.back()"); return {"requested":True}
def go_forward(context, session): _evaluate(session,"history.forward()"); return {"requested":True}
def refresh_page(context, session): _call(session,"Page.reload",{"ignoreCache":False}); return {"requested":True}
def wait_page(context, session, state, timeout_ms):
    wanted = "complete" if state == "complete" else "interactive"; deadline = time.monotonic() + int(timeout_ms)/1000
    while time.monotonic() < deadline:
        current = _evaluate(session, "document.readyState")
        if current == "complete" or (wanted == "interactive" and current == "interactive"): return {"state": current}
        time.sleep(.1)
    raise TimeoutError("等待页面就绪超时")
def wait_element(context, session, selector, frame_selector, timeout_ms):
    deadline = time.monotonic() + int(timeout_ms)/1000
    expression = _element_expression(selector, "return true;", frame_selector)
    while time.monotonic() < deadline:
        try:
            if _evaluate(session, expression): return {"found": True, "selector": selector}
        except Exception: pass
        time.sleep(.1)
    raise TimeoutError("等待元素超时")
def click_element(context, session, selector, frame_selector):
    return _evaluate(session, _element_expression(selector, 'e.scrollIntoView({block:"center"}); e.click(); return {clicked:true};', frame_selector))
def input_text(context, session, selector, text, frame_selector):
    body = f"""e.focus(); const old=e.value; e.value={json.dumps(text)}; e.dispatchEvent(new InputEvent("input",{{bubbles:true,inputType:"insertText",data:{json.dumps(text)}}})); e.dispatchEvent(new Event("change",{{bubbles:true}})); return {{previous:old,value:e.value}};"""
    return _evaluate(session, _element_expression(selector, body, frame_selector))
def select_option(context, session, selector, value, frame_selector):
    body = f"""e.value={json.dumps(value)}; e.dispatchEvent(new Event("change",{{bubbles:true}})); return {{value:e.value}};"""
    return _evaluate(session, _element_expression(selector, body, frame_selector))
def read_text(context, session, selector, frame_selector): return _evaluate(session, _element_expression(selector, "return e.innerText ?? e.textContent ?? '';", frame_selector))
def read_attribute(context, session, selector, attribute, frame_selector): return _evaluate(session, _element_expression(selector, f"return e.getAttribute({json.dumps(attribute)});", frame_selector))
def read_table(context, session, selector, frame_selector):
    return _evaluate(session, _element_expression(selector, "return Array.from(e.rows).map(r=>Array.from(r.cells).map(c=>(c.innerText||'').trim()));", frame_selector))
def list_tabs(context, session):
    return [{"target_id": row.get("id"), "title": row.get("title"), "url": row.get("url")} for row in _http_json(_endpoint(session)+"/json") if row.get("type")=="page"]
def switch_tab(context, session, target_id):
    rows = list_tabs(context, session); row = next((item for item in rows if item["target_id"] == target_id), None)
    if not row: raise RuntimeError("标签页不存在")
    _http_get(_endpoint(session)+"/json/activate/"+target_id); return dict(session, target_id=target_id, title=row["title"], url=row["url"])
def set_download_directory(context, session, path):
    target=os.path.abspath(path); os.makedirs(target,exist_ok=True); _call(session,"Browser.setDownloadBehavior",{"behavior":"allow","downloadPath":target,"eventsEnabled":True}); return {"directory":target}
def pick_element(context, session, timeout_ms):
    script = """new Promise((resolve)=>{const h=(e)=>{e.preventDefault();e.stopPropagation();const x=e.target;const p=[];let n=x;while(n&&n.nodeType===1&&p.length<5){let s=n.tagName.toLowerCase();if(n.id){s+="#"+CSS.escape(n.id);p.unshift(s);break}const q=n.parentElement?[...n.parentElement.children].filter(v=>v.tagName===n.tagName).indexOf(n)+1:1;s+=`:nth-of-type(${q})`;p.unshift(s);n=n.parentElement}document.removeEventListener("click",h,true);resolve({selector:p.join(" > "),text:(x.innerText||x.getAttribute("aria-label")||"").trim().slice(0,160),tag:x.tagName.toLowerCase()})};document.addEventListener("click",h,true)})"""
    return _evaluate(session, script, await_promise=True)
def close_browser(context, session):
    target = _target(session)
    if target: _http_get(_endpoint(session)+"/json/close/"+target["id"])
    return {"closed": bool(target)}
'''


EXCEL_SOURCE = r'''
"""Dependency-free CSV and Office Open XML workbook operations."""
import csv, json, os, tempfile, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MAIN="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL="http://schemas.openxmlformats.org/package/2006/relationships"
DOCREL="http://schemas.openxmlformats.org/officeDocument/2006/relationships"

def _rows(value):
    if not isinstance(value, list) or any(not isinstance(row, list) for row in value): raise ValueError("数据必须是二维列表")
    return value
def read_csv(context, path, encoding, delimiter, has_header):
    with open(path, "r", encoding=encoding or "utf-8-sig", newline="") as stream: rows=list(csv.reader(stream, delimiter=(delimiter or ",")[0]))
    return {"headers": rows[0] if has_header and rows else [], "rows": rows[1:] if has_header and rows else rows, "row_count": max(0,len(rows)-(1 if has_header and rows else 0))}
def write_csv(context, path, rows, encoding, delimiter):
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True); fd,temp=tempfile.mkstemp(prefix=".easycode-csv-",dir=target.parent); os.close(fd)
    try:
        with open(temp,"w",encoding=encoding or "utf-8-sig",newline="") as stream: csv.writer(stream,delimiter=(delimiter or ",")[0]).writerows(_rows(rows))
        os.replace(temp,target)
    finally:
        if os.path.exists(temp): os.unlink(temp)
    return {"path":str(target.resolve()),"row_count":len(rows)}
def _shared(archive):
    try:
        root=ET.fromstring(archive.read("xl/sharedStrings.xml")); return ["".join(node.text or "" for node in item.iter(f"{{{MAIN}}}t")) for item in root]
    except KeyError:return []
def _sheet_path(archive,name):
    book=ET.fromstring(archive.read("xl/workbook.xml")); rels=ET.fromstring(archive.read("xl/_rels/workbook.xml.rels")); links={r.attrib["Id"]:r.attrib["Target"] for r in rels}
    sheets=book.find(f"{{{MAIN}}}sheets"); sheets=[] if sheets is None else sheets
    row=next((s for s in sheets if not name or s.attrib.get("name")==name),None)
    if row is None: raise ValueError("工作表不存在")
    target=links[row.attrib[f"{{{DOCREL}}}id"]].lstrip("/"); return target if target.startswith("xl/") else "xl/"+target, row.attrib.get("name","")
def read_xlsx(context,path,sheet_name,has_header):
    with zipfile.ZipFile(path) as archive:
        shared=_shared(archive); sheet_path,actual=_sheet_path(archive,sheet_name); root=ET.fromstring(archive.read(sheet_path)); rows=[]
        for row in root.iter(f"{{{MAIN}}}row"):
            values=[]
            for cell in row.findall(f"{{{MAIN}}}c"):
                kind=cell.attrib.get("t"); value=cell.find(f"{{{MAIN}}}v"); raw="" if value is None else value.text or ""
                inline=cell.find(f"{{{MAIN}}}is"); inline_text="" if inline is None else "".join(node.text or "" for node in inline.iter(f"{{{MAIN}}}t"))
                values.append(shared[int(raw)] if kind=="s" and raw else inline_text if kind=="inlineStr" else raw)
            rows.append(values)
    return {"sheet":actual,"headers":rows[0] if has_header and rows else [],"rows":rows[1:] if has_header and rows else rows,"row_count":max(0,len(rows)-(1 if has_header and rows else 0))}
def list_sheets(context,path):
    with zipfile.ZipFile(path) as archive:
        book=ET.fromstring(archive.read("xl/workbook.xml")); sheets=book.find(f"{{{MAIN}}}sheets"); return [s.attrib.get("name","") for s in ([] if sheets is None else sheets)]
def write_xlsx(context,path,rows,sheet_name):
    rows=_rows(rows); target=Path(path); target.parent.mkdir(parents=True,exist_ok=True); fd,temp=tempfile.mkstemp(prefix=".easycode-xlsx-",dir=target.parent); os.close(fd)
    def letters(index):
        value=""
        while index: index,remainder=divmod(index-1,26); value=chr(65+remainder)+value
        return value
    worksheet=ET.Element("worksheet",xmlns=MAIN); data=ET.SubElement(worksheet,"sheetData")
    for row_index,row in enumerate(rows,1):
        row_node=ET.SubElement(data,"row",r=str(row_index))
        for column_index,value in enumerate(row,1):
            reference=f"{letters(column_index)}{row_index}"
            if isinstance(value,(int,float)) and not isinstance(value,bool): cell=ET.SubElement(row_node,"c",r=reference); ET.SubElement(cell,"v").text=str(value)
            else: cell=ET.SubElement(row_node,"c",r=reference,t="inlineStr"); inline=ET.SubElement(cell,"is"); ET.SubElement(inline,"t").text="" if value is None else str(value)
    try:
        with zipfile.ZipFile(temp,"w",compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml","""<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>""")
            archive.writestr("_rels/.rels","""<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>""")
            safe_name=str(sheet_name or "Sheet1").replace("&","&amp;").replace("<","&lt;").replace('"',"&quot;")[:31]
            archive.writestr("xl/workbook.xml",f"""<workbook xmlns="{MAIN}" xmlns:r="{DOCREL}"><sheets><sheet name="{safe_name}" sheetId="1" r:id="rId1"/></sheets></workbook>""")
            archive.writestr("xl/_rels/workbook.xml.rels",f"""<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{DOCREL}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>""")
            archive.writestr("xl/worksheets/sheet1.xml",ET.tostring(worksheet,encoding="utf-8",xml_declaration=True))
        os.replace(temp,target)
    finally:
        if os.path.exists(temp): os.unlink(temp)
    return {"path":str(target.resolve()),"sheet":sheet_name or "Sheet1","row_count":len(rows)}
def filter_rows(context,rows,column_index,operator,value):
    index=int(column_index); result=[]
    for row in _rows(rows):
        current=row[index] if index<len(row) else None
        matched=current==value if operator=="equals" else str(value) in str(current) if operator=="contains" else float(current)>float(value) if operator=="greater" else float(current)<float(value)
        if matched: result.append(row)
    return result
def sort_rows(context,rows,column_index,descending):
    index=int(column_index); return sorted(_rows(rows),key=lambda row:(index>=len(row),str(row[index]) if index<len(row) else ""),reverse=bool(descending))
def rows_to_records(context,headers,rows): return [dict(zip(headers,row)) for row in _rows(rows)]
'''


def browser_spec() -> PackageSpec:
    package = f"{PUBLISHER_ID}.browserdom"
    permissions = ("host.launch_application", "network", "filesystem.write")
    session = lambda fid: _parameter(fid, "session", "浏览器会话", "json", control="json")
    text = lambda fid, name, label, required=True, default=None: _parameter(fid, name, label, required=required, default=default)
    definitions: list[dict[str, Any]] = []
    def add(name: str, label: str, description: str, params: list[dict[str, Any]], result: str = "json", timeout: int = 30_000, function_permissions: tuple[str, ...] = ("network",)):
        definitions.append(function_contract(package, name, f"浏览器.{label}", description, params, result=result, permissions=function_permissions, timeout=timeout))
    fid=f"{package}.launch_browser"; add("launch_browser","启动浏览器","启动带本地 DevTools 连接的 Edge 或 Chrome。",[text(fid,"browser","浏览器",False,"edge"),text(fid,"start_url","起始地址",False,"about:blank")],function_permissions=("host.launch_application","network"))
    fid=f"{package}.connect_browser"; add("connect_browser","连接浏览器","连接已开启 DevTools 的本机浏览器。",[text(fid,"endpoint","连接地址",False,"http://127.0.0.1:9222")])
    fid=f"{package}.open_url"; add("open_url","打开网页","打开地址并按页面状态等待。",[session(fid),text(fid,"url","网页地址"),text(fid,"wait_state","等待状态",False,"complete")])
    for name,label in (("go_back","后退"),("go_forward","前进"),("refresh_page","刷新")):
        fid=f"{package}.{name}"; add(name,label,f"让当前标签页{label}。",[session(fid)])
    fid=f"{package}.wait_page"; add("wait_page","等待页面","等待页面进入交互或完成状态。",[session(fid),text(fid,"state","页面状态",False,"complete"),_parameter(fid,"timeout_ms","超时（毫秒）","int64",required=False,default=30000,control="number")])
    for name,label in (("wait_element","等待元素"),("click_element","点击元素"),("read_text","读取文字"),("read_table","读取表格")):
        fid=f"{package}.{name}"; params=[session(fid),text(fid,"selector","CSS 选择器"),text(fid,"frame_selector","iframe 选择器",False,"")]
        if name=="wait_element": params.append(_parameter(fid,"timeout_ms","超时（毫秒）","int64",required=False,default=30000,control="number"))
        add(name,label,"通过 DOM 选择器操作元素；支持同源 iframe。",params,result="string" if name=="read_text" else "json")
    fid=f"{package}.input_text"; add("input_text","填写文本","填写输入控件并派发 input/change 事件。",[session(fid),text(fid,"selector","CSS 选择器"),text(fid,"text","文本"),text(fid,"frame_selector","iframe 选择器",False,"")])
    fid=f"{package}.select_option"; add("select_option","选择选项","按 value 选择下拉选项。",[session(fid),text(fid,"selector","CSS 选择器"),text(fid,"value","选项值"),text(fid,"frame_selector","iframe 选择器",False,"")])
    fid=f"{package}.read_attribute"; add("read_attribute","读取属性","读取 DOM 元素属性。",[session(fid),text(fid,"selector","CSS 选择器"),text(fid,"attribute","属性名"),text(fid,"frame_selector","iframe 选择器",False,"")],result="string")
    fid=f"{package}.list_tabs"; add("list_tabs","列出标签页","读取所有页面标签页。",[session(fid)])
    fid=f"{package}.switch_tab"; add("switch_tab","切换标签页","切换到指定标签页并返回新会话。",[session(fid),text(fid,"target_id","标签页 ID")])
    fid=f"{package}.set_download_directory"; add("set_download_directory","设置下载目录","显式设置后续浏览器下载的本机目录。",[session(fid),text(fid,"path","下载目录")],function_permissions=("network","filesystem.write"))
    fid=f"{package}.pick_element"; add("pick_element","拾取网页元素","在页面点击一个元素并返回简短稳定选择器。",[session(fid),_parameter(fid,"timeout_ms","超时（毫秒）","int64",required=False,default=30000,control="number")],timeout=60_000)
    fid=f"{package}.close_browser"; add("close_browser","关闭标签页","关闭当前标签页。",[session(fid)])
    return PackageSpec("browser",package,"浏览器 DOM 自动化","Edge/Chrome DOM 操作、元素拾取、标签页、iframe 与结构化数据读取。",permissions,{"level":"local_lan","rules":[{"rule_id":"local-cdp","hosts":["127.0.0.1","localhost"],"ports":[9222]}]},tuple(definitions),BROWSER_SOURCE,"浏览器不会静默安装运行时；导入、信任、密封并启用后，从普通函数库的“扩展”页使用。默认连接本机 9222 端口。")


def excel_spec() -> PackageSpec:
    package=f"{PUBLISHER_ID}.tabulardata"; permissions=("filesystem.read","filesystem.write")
    definitions=[]
    def add(name,label,description,params,result="json",permissions_for_function=permissions): definitions.append(function_contract(package,name,f"表格.{label}",description,params,result=result,permissions=permissions_for_function))
    fid=f"{package}.read_csv"; add("read_csv","读取 CSV","读取 CSV 为表头与二维列表。",[_parameter(fid,"path","文件路径"),_parameter(fid,"encoding","编码",required=False,default="utf-8-sig"),_parameter(fid,"delimiter","分隔符",required=False,default=","),_parameter(fid,"has_header","首行为表头","bool",required=False,default=True,control="checkbox")],permissions_for_function=("filesystem.read",))
    fid=f"{package}.write_csv"; add("write_csv","写入 CSV","原子写入二维列表。",[_parameter(fid,"path","文件路径"),_parameter(fid,"rows","二维数据","json",control="json"),_parameter(fid,"encoding","编码",required=False,default="utf-8-sig"),_parameter(fid,"delimiter","分隔符",required=False,default=",")],permissions_for_function=("filesystem.write",))
    fid=f"{package}.read_xlsx"; add("read_xlsx","读取 Excel","无需 Office 读取 xlsx 工作表。",[_parameter(fid,"path","Excel 文件"),_parameter(fid,"sheet_name","工作表",required=False,default=""),_parameter(fid,"has_header","首行为表头","bool",required=False,default=True,control="checkbox")],permissions_for_function=("filesystem.read",))
    fid=f"{package}.write_xlsx"; add("write_xlsx","写入 Excel","无需 Office 原子写入 xlsx 工作簿。",[_parameter(fid,"path","Excel 文件"),_parameter(fid,"rows","二维数据","json",control="json"),_parameter(fid,"sheet_name","工作表",required=False,default="Sheet1")],permissions_for_function=("filesystem.write",))
    fid=f"{package}.list_sheets"; add("list_sheets","列出工作表","列出 xlsx 中的工作表名称。",[_parameter(fid,"path","Excel 文件")],permissions_for_function=("filesystem.read",))
    fid=f"{package}.filter_rows"; add("filter_rows","筛选行","按列号和值筛选二维列表。",[_parameter(fid,"rows","二维数据","json",control="json"),_parameter(fid,"column_index","列号","int64",control="number"),_parameter(fid,"operator","条件",required=False,default="equals"),_parameter(fid,"value","比较值","json",control="json")],permissions_for_function=())
    fid=f"{package}.sort_rows"; add("sort_rows","排序行","按列号排序二维列表。",[_parameter(fid,"rows","二维数据","json",control="json"),_parameter(fid,"column_index","列号","int64",control="number"),_parameter(fid,"descending","降序","bool",required=False,default=False,control="checkbox")],permissions_for_function=())
    fid=f"{package}.rows_to_records"; add("rows_to_records","转为记录列表","将表头与二维数据组合为记录列表。",[_parameter(fid,"headers","表头","json",control="json"),_parameter(fid,"rows","二维数据","json",control="json")],permissions_for_function=())
    return PackageSpec("excel",package,"Excel 与 CSV","本机 CSV、xlsx 读取及可组合的数据筛选、排序和转换。",permissions,{"level":"none","rules":[]},tuple(definitions),EXCEL_SOURCE,"这是普通可导入扩展包；不要求安装 Office，不访问网络。首期 xlsx 为可靠只读，CSV 支持原子写入。")


SPECS = {item.key:item for item in (browser_spec(),excel_spec())}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+"\n",encoding="utf-8")


def build_source_package(spec: PackageSpec, parent: Path) -> Path:
    authoring=parent/f"{spec.key}-authoring-project"; VNextWorkspaceManager().open(str(authoring),initialize=True)
    created=VNextExtensionRegistry.scaffold(str(authoring),package_id=spec.package_id,publisher_id=PUBLISHER_ID,publisher_name="EasyCode",display_name=spec.display_name,description=spec.description,scope="project")
    root=Path(created["path"]); manifest_value=json.loads((root/MANIFEST_FILE).read_text(encoding="utf-8"))
    manifest_value["permissions"]=list(spec.permissions); manifest_value["network"]=spec.network
    manifest_value["variants"][0]["entrypoints"]={row["function_id"]:row["function_id"].rsplit(".",1)[-1] for row in spec.contracts}
    manifest=ExtensionManifestV1.model_validate(manifest_value)
    contracts=FunctionContractFileV1.model_validate({"contract_schema_version":1,"contribution_id":f"{spec.package_id}.functions","functions":list(spec.contracts)})
    write_json(root/MANIFEST_FILE,manifest.model_dump(mode="json",exclude_none=True)); write_json(root/"contracts"/"functions.json",contracts.model_dump(mode="json"))
    (root/"src"/"main.py").write_text(spec.source,encoding="utf-8"); (root/"README.md").write_text(f"# {spec.display_name}\n\n{spec.readme}\n",encoding="utf-8")
    identity=AuthorSigningKeyStore().get_or_create(f"extension:{PUBLISHER_ID}"); write_json(root/MANIFEST_SIGNATURE_FILE,sign_manifest(root,manifest,identity)); return root


def remove_existing(project: Path, spec: PackageSpec, scope: str) -> None:
    try: package=VNextExtensionRegistry.package(str(project),spec.package_id,scope)
    except RuntimeFailure: return
    if package.get("enabled"): VNextExtensionRegistry.disable(str(project),spec.package_id,scope)
    VNextExtensionRegistry.delete_package(str(project),spec.package_id,scope)


def install(project: Path, spec: PackageSpec, scope: str="project") -> dict[str,Any]:
    remove_existing(project,spec,scope)
    with tempfile.TemporaryDirectory(prefix=f"EasyCode-{spec.key}-") as temporary:
        source=build_source_package(spec,Path(temporary)); imported=VNextExtensionRegistry.import_package(str(project),source_path=str(source),scope=scope)
    VNextExtensionRegistry.trust(str(project),spec.package_id,scope,mode="explicit"); sealed=VNextExtensionRegistry.build_sealed(str(project),spec.package_id,scope); enabled=VNextExtensionRegistry.enable(str(project),spec.package_id,scope)
    definitions,errors=VNextExtensionRegistry.definitions(str(project))
    return {"package_id":spec.package_id,"scope":scope,"imported":bool(imported.get("imported")),"signature_verified":bool(imported["package"].get("signature_verified")),"enabled":bool(enabled.get("enabled")),"sealed_formats":[item.get("format") for item in sealed.get("artifacts") or []],"function_ids":[row["function_id"] for row in definitions if row.get("package_id")==spec.package_id],"errors":errors}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("package",choices=sorted(SPECS)); parser.add_argument("action",choices=("build","install","remove","status")); parser.add_argument("--project",type=Path); parser.add_argument("--output",type=Path); parser.add_argument("--scope",choices=("project","user"),default="project"); args=parser.parse_args(); spec=SPECS[args.package]
    if args.action=="build":
        if args.output is None: parser.error("build 需要 --output")
        result={"built":True,"package_path":str(build_source_package(spec,args.output.resolve()))}
    else:
        if args.project is None: parser.error(f"{args.action} 需要 --project")
        project=args.project.resolve()
        if args.action=="install": result=install(project,spec,args.scope)
        elif args.action=="remove": remove_existing(project,spec,args.scope); result={"removed":True,"package_id":spec.package_id}
        else: result=VNextExtensionRegistry.package(str(project),spec.package_id,args.scope)
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str)); return 0


if __name__=="__main__": raise SystemExit(main())
