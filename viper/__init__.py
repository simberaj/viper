
import http.server
import sys
import os
import logging
import urllib.parse
import cgi
import random
import collections
import json

log = logging.getLogger(__name__)

# TODO:
# module design
# more sophisticated UI segments
# integration of Bootstrap
# Dashboard as a subclass of UI

logging.basicConfig(level=logging.INFO)

DEFAULT_PORT = 1711

DEFAULT_ROOT = b'''<html>
  <body>
    Viper server started successfully.
  </body>
</html>'''

MIME_TYPES = {
  'html' : 'text/html'
}

RAND_BITS = 128

FX_PREFIX = '_viper_'

FORM_MIME_TYPE = 'application/x-www-form-urlencoded'

def generateID(ref, no=0):
  return '{}-{:0x}-{}'.format(ref, random.getrandbits(RAND_BITS), no)

class HTTP:
  def __init__(self, handler=None, port=DEFAULT_PORT, directory=None):
    self.port = port
    self._handler = handler if handler else Handler
    if directory:
      self.handler.directory = directory
    self.server = http.server.HTTPServer(('', self.port), self.handler)
    
  @property
  def handler(self):
    return self._handler
    
  def run(self):
    try:
      log.info('server starting up')
      self.server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
      log.info('server shutting down by operator interrupt')
      sys.exit()
    
    
class Handler(http.server.BaseHTTPRequestHandler):
  listeners = {}
  mimes = {}
  directory = os.getcwd()

  def do_GET(self):
    req = urllib.parse.urlparse(self.path)
    if req.query:
      self.handleRequest(req.path[1:], dict(qc.split("=") for qc in req.query.split("&")))
    elif req.path == '/':
      self.sendRoot()
    elif '.' in req.path:
      self.sendFile(req.path[1:])
    else:
      log.info('unknown GET %s', self.path)
      self.send_error(404)
  
  def do_POST(self):
    ctype = self.headers['Content-Type']
    if ctype == FORM_MIME_TYPE:
      cgiFields = cgi.FieldStorage(
        fp=self.rfile, 
        headers=self.headers,
        environ={
          'REQUEST_METHOD' : 'POST',
          'CONTENT_TYPE' : self.headers['Content-Type'],
        }
      )
      data = dict((k, cgiFields[k].value) for k in cgiFields.keys())
    else:
      data = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode('utf8'))
    self.handleRequest(self.path[1:], data)
    
            
  def sendRoot(self):
    log.info('serving root page')
    self.sendOKHeaders('text/html')
    self.wfile.write(self.getRoot())
  
  def sendFile(self, path):
    try:
      ext = os.path.splitext(path)[1][1:]
      with open(os.path.join(self.directory, path), 'rb') as ffile:
        log.info('serving file %s', path)
        self.sendOKHeaders(MIME_TYPES.get(ext, 'text/plain'))
        self.wfile.write(ffile.read())
    except IOError:
      log.info('unknown file %s', path)
      self.send_error(404)
  
  def handleRequest(self, name, content):
    if name in self.listeners:
      log.info('serving request %s: %s', name, content)
      self.sendOKHeaders(self.mimes[name])
      self.wfile.write(self.listeners[name](**content))
    else:
      log.info('unknown request %s', name)
      self.send_error(404)
    
  def sendOKHeaders(self, mimeType):
    self.send_response(200)
    self.send_header('Content-Type', mimeType)
    self.end_headers()
    
  
  @staticmethod
  def defaultGetRoot():
    return DEFAULT_ROOT
    
  getRoot = staticmethod(defaultGetRoot)
  
  @classmethod
  def listen(cls, name, listener, mime='application/json'):
    cls.listeners[name] = listener
    cls.mimes[name] = mime
  
  @classmethod
  def root(cls, fx):
    cls.getRoot = staticmethod(fx)
    
    
class Application:
  def __init__(self, ui, server):
    self.ui = ui
    self.server = server
  
  def run(self):
    self.http = HTTP()
    self.http.handler.root(self.ui.root)
    for name, hook, mime in self.server.gates():
      self.http.handler.listen(name, hook, mime)
    self.http.run()

    
class UI:
  start = '''<html>
  <head>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/4.8.0/d3.min.js"></script>
  </head>
  <body>'''
  end = '</body></html>'

  def __init__(self, *items):
    self.items = items
  
  def root(self):
    return (self.start + 
      '\n\n'.join(item.html() for item in self.items) + 
      self.code(self.items) + 
    self.end).encode('utf8')
    
  def code(self, items):
    return '<script type="text/javascript">' + self.ownCode() + '\n\n'.join(self.codeFor(item) for item in items) + '</script>'
  
  def ownCode(self):
    return '''
      _viperFunctions = {};
    
      function _viperSendInput(id, value) {
        console.log(id);
        console.log(value);
        var request = {
          "type" : "request",
          "request" : "input",
          "input" : {}
        };
        request.input[id] = value;
        d3.request("input").mimeType("application/json").post(
          JSON.stringify(request),
          function (error, response) {
            if (error) console.warn(error);
            else _viperUpdateOutputs(JSON.parse(response.response));
          }
        );
      }
      
      function _viperUpdateOutputs(json) {
        if (json.output != null) {
          for (var id in json.output) {
            _viperFunctions[id](json.output[id]);
          }
        }
      }
    '''

  def codeFor(self, item):
    return '''// code for %s
    %s = %s;
    _viperFunctions["%s"] = %s;''' % (
      item.ref, item.fid, item.code(), item.ref, item.fid
    )
    

class UISegment:
  DEFAULT_BLOCKED_ATTRS = ['onchange']
  BLOCKED_ATTRS = []

  def __init__(self, ref):
    self.ref = ref
    self.id = generateID(ref)
  
  @property
  def fid(self):
    return FX_PREFIX + self.id.replace('-', '')
  
  def processDirectAttrributes(self, fmtargs):
    for attr in self.DEFAULT_BLOCKED_ATTRS + self.BLOCKED_ATTRS:
      if attr in fmtargs:
        toremove.append(attr)
    for key, val in fmtargs.items():
      if not val:
        toremove.append(key)
      elif val is True:
        fmtargs[key] = key
    return fmtargs
  
  @staticmethod
  def formatAttributes(attrs):
    return ' '.join('{}="{}"'.format(key, val) for key, val in attrs.items())
  

    
class Input(UISegment):
  def code(self):
    return '''function() {_viperSendInput("%s", %s);}''' % (self.id, self.getterCode())
  
  def callCode(self):
    return self.fid + '();'
  
  
class TextInput(Input):
  BLOCKED_ATTRS = ['type', 'name']
  REQUIRED_ATTRS = ['value']

  def __init__(self, ref, label=None, updateMode='onchange', **fmtattrs):
    super().__init__(ref)
    self.label = label
    self.attrs = self.processDirectAttrributes(fmtattrs)
    self.attrs[updateMode] = self.callCode()
  
  def html(self):
    return self.labelPartHTML() + '<input type="text" id="{id}" name="{id}" {attrs}>'.format(
      id=self.id, attrs=self.formatAttributes(self.attrs)
    )
  
  def labelPartHTML(self):
    return ''
  
  def getterCode(self):
    return 'd3.select("#%s").node().value' % self.id
  

class Output(UISegment):
  pass
    
class TextOutput(Output):
  def html(self):
    return '''<span id="{}"></span>'''.format(self.id)
  
  def code(self):
    return '''function(value) {d3.select("#%s").text(value);}''' % self.id
    
    
    
class Server:
  def __init__(self, bindings={}):
    self._inputBindings = collections.defaultdict(list)
    self._outputMethods = {}
    self._outputArguments = {}
    self._registerBindings(bindings)
    
  def gates(self):
    return [
      ('input', self.processInput, 'application/json')
    ]
  
  def processInput(self, input={}, **rest):
    print(input)
    print(self._inputBindings)
    inputs = {}
    outputsToUpdate = set()
    for key in input:
      trueKey = key.split('-')[0]
      outputsToUpdate.update(self._inputBindings[trueKey])
      inputs[trueKey] = input[key]
    print(outputsToUpdate)
    outputs = {}
    for id in outputsToUpdate:
      outputs[id] = self._outputMethods[id](*[inputs[key] for key in self._outputArguments[id]])
    print(outputs)
    return json.dumps({'output' : outputs}).encode('utf8')
  
  def _registerBindings(self, bindings):
    for output in bindings:
      method, inputs = bindings[output]
      if isinstance(inputs, str): inputs = [inputs]
      for inp in inputs:
        self._inputBindings[inp].append(output)
      self._outputMethods[output] = method
      self._outputArguments[output] = inputs
