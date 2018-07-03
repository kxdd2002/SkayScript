import os

# 读取文件
def readLine(fileName,handleLine,r=[],isShowLine=False):
	with open(fileName,'r') as fb:
		n = 0
		for line in fb.readlines():
			n+=1
			hr = handleLine(n,line,isShowLine)
			if hr :
				if type(hr)==list:
					r += hr
				else:
					r.append(hr)
	return r
import re

# 词法分析规则
re_Pat = re.compile(r'\s*((//.*)|([0-9]+)|("(?:\\"|\\\\|\\n|[^"])*")|([a-z_A-Z][a-z_A-Z0-9]*)|(==|\*\*|>=|<=|&&|\|\||[^A-Za-z0-9_]))?')

# 词法分析
def lexicalAnalysis(no,line,isShowLine=False):
	if isShowLine:
		print(no,line)
	rl = []
	b = 0
	end = len(line)
	while b<end:
		rre = re_Pat.match(line[b:end])
		b += rre.end()
		t = 'commit' if rre.group(2) else 'num' if rre.group(3) else 'str' if rre.group(4) else 'id' if rre.group(6) else 'id'
		if rre.group(1):
			rl.append((no,t,rre.group(1)))
	rl.append((no,'EOL','\n'))
	if isShowLine:
		for rrr in rl:
			print(rrr)
	return rl

# 词法读取
class LexerReader(object):
	def __init__(self,lexer):
		self.lexer = lexer
		self.cur = 0
		self.pre = 0
		self.len = len(lexer)
	def read(self):
		if self.cur >= self.len:
			return False
		k = self.lexer[self.cur]
		self.cur += 1
		self.pre = 0
		# print('read',k,self.cur,self.pre)
		return k
	def seed(self,step=0):
		if self.cur+step+self.pre >= self.len:
			return False
		k = self.lexer[self.cur+step+self.pre]
		# print('seed',k,self.cur,self.pre,step)
		return k
	def nextSeed(self):
		self.pre += 1
	def r(self,p=False):
			return self.seed() if p else self.read()
	def seedClear(self):
		self.pre = 0

# 非裁剪语法树分支名集合(全局)
noCutTreeTypes = []

# 语法分析工具
class P(object):
	def __init__(self,tag=None):
		self.tag = tag
		self.args = []
	def parse(self,reader,rps):
		ps = []
		if self.tag:
			ps.append(self.tag)
		for p in self.args:
			p.parse(reader,ps)
		self.addTree(rps,ps)
	def ask(self,reader):
		p = self.args[0]
		if p :
			return p.ask(reader)
	def setTag(self,tag):
		self.tag = tag
		return self
	def which(self,parser):
		return WhichParser().add(self).add(parser) if type(self)!=WhichParser else self.add(parser)
	def add(self,other):
		self.args.append(other)
		return self
	def __or__(self,parser):
		return self.which(parser)
	def __add__(self,other):
		return self.add(other)
	def loop(self,onlyOne=False):
		return LoopParser(self,onlyOne)
	def noCut(self):
		if self.tag and not self.tag in noCutTreeTypes:
			noCutTreeTypes.append(self.tag)
		return self
	def addTree(self,tree,subTree):
		if (self.tag or (subTree and len(subTree)>1 and type(subTree[0])==str)) and tree:
			# print('>',self.tag,type(self),tree,'||',subTree)
			if subTree[0] in noCutTreeTypes:
				tree.append(subTree)
			else:
				tree.append(subTree if len(subTree)>2 else subTree[1] if len(subTree)==2 else None)
			# tree.append(subTree)
		else:
			# print('+',self.tag,type(self),tree,'||',subTree,'???')
			tree += subTree
class WhichParser(P):
	def __init__(self):
		self.args = []
		self.tag = None
	def parse(self,reader,rps):
		ps = []
		if self.tag:
			ps.append(self.tag)
		p = self.ask(reader)
		if p:
			p.parse(reader,ps)
		else:
			raise ValueError('Parser for %s error ! in line: %d' % (self.tag,reader.seed(0)[0]))
		self.addTree(rps,ps)
	def ask(self,reader):
		for p in self.args :
			if p.ask(reader):
				return p
class LoopParser(P):
	def __init__(self,parser,onlyOne=False):
		self.parser = parser
		self.onlyOne = onlyOne
		self.tag = None
	def parse(self,reader,rps):
		ps = []
		if self.tag:
			ps.append(self.tag)
		while (self.parser.ask(reader)):
			self.parser.parse(reader,ps)
			if self.onlyOne:
				break
		self.addTree(rps,ps)
	def ask(self,reader):
		while (self.parser.ask(reader)):
			self.parser.nextSeed()
		return True
class LeafParser(P):
	def __init__(self,name,token=None,reserved = []):
		self.name = name
		self.token = token
		self.reserved = reserved
	def parse(self,reader,ps):
		s = reader.read()
		if self.name!='token':
			# print((self.name,s))
			ps.append((self.name,s[2]))
	def ask(self,reader):
		s = reader.seed()
		if s:
			if (s in self.reserved) and self.name == 'id':
				return False
			r = s[1]==self.name if (self.name!='token' and not self.token) else self.token==s[2]
			return r
def token(token):
	return P()+LeafParser('token',token)
def id(token=None,reserved=[]):
	return P()+LeafParser('id',token,reserved)
def words():
	return P()+LeafParser('str')
def num():
	return P()+LeafParser('num')
class OP(P):
	def __init__(self,parser,optRules={}):
		self.name = 'opt'
		self.parser = parser
		self.optList = optRules
	def parse(self,reader,ps,level=0):
		# print('in .. ',self.ask(reader))
		# print('pos',reader.cur)
		while (self.ask(reader)):
			optInfo = self.ask(reader)
			if optInfo[0] < level:
				break
			# print('next .. ',ps)
			self.doSwift(reader,ps)
		# print('out .. ',ps)
		# print('pos',reader.cur)
	def askNextOpt(self,curInfo,nextInfo):
		if curInfo[1]: # 此算法是否是从左运算的
			return curInfo[0] < nextInfo[0]
		else:
			return curInfo[0] <= nextInfo[0]
	def doSwift(self,reader,ps):
		optInfo = self.ask(reader)
		s = reader.read()
		rps = []
		rps.append('opt')
		rps.append(s)
		self.parser.parse(reader,rps)
		nsInfo = self.ask(reader)
		# print('doSwift',s,optInfo,reader.seed(),nsInfo,(nsInfo and self.askNextOpt(optInfo,nsInfo)))
		# print('pos',reader.cur)
		if (nsInfo and self.askNextOpt(optInfo,nsInfo)):
			self.parse(reader,rps,nsInfo[0])
		ps.append(rps)
	def ask(self,reader):
		s = reader.seed()
		if s and len(s)>2 and s[2] in self.optList:
			return self.optList[s[2]]
		return False

# 语法分析规则1(自顶向下)
# primary    : "(" exp ")" | NUMBER 
# involution        : primary {"**" primary}
# mul        : involution {("*"|"/") involution}
# exp        : mul {("+"|"-") mul}
class ParserRules(object):
	def __init__(self,reader):
		self.reader = reader
		self.exp = P('exp')
		self.primary = P('primary') + (token('(') + self.exp + token(')')) | num()
		self.involution = P('mul') + self.primary + ( id('**') + self.primary ).loop()
		self.mul = P('mul') + self.involution + ( (id('*')|id('/')) + self.involution ).loop()
		self.exp = self.exp + self.mul + ((id('+') | id('-')) + self.mul ).loop()
	def parse(self):
		ps = []
		self.exp.parse(self.reader,ps)
		return ps

# 语法分析规则2(同1)（算符部分自底向上）
# primary    : "(" exp ")" | NUMBER 
# exp        : primary {OP primary}
class ParserRules2(object):
	def __init__(self,reader):
		self.reader = reader
		optRules = self.initOptRules()
		self.exp = P('exp')
		self.primary = P('primary') + (token('(') + self.exp + token(')')) | num()
		self.exp = self.exp + self.primary + OP(self.primary,optRules)
	def initOptRules(self):
		optRules = {}
		optRules['+'] = (1,True)
		optRules['-'] = (1,True)
		optRules['*'] = (2,True)
		optRules['/'] = (2,True)
		optRules['**'] = (3,False)
		return optRules
	def parse(self):
		ps = []
		self.exp.parse(self.reader,ps)
		return ps

# 语法分析规则3 
# primary    : "(" expr ")" | NUMBER | IDENTIFIER | STRING
# factor     : "-" primary | primary
# expr       : factor { OP factor }
# block      : "{" [ statement ] {(";" | EOL) [ statement ]} "}"
# simple     : expr
# statement  : "if" expr block [ "else" block ]
#            | "while" expr block
#            | simple
# program    : [ statement ] (";" | EOL)
class ParserRules3(object):
	def __init__(self,reader):
		self.reader = reader
		optRules = self.initOptRules()
		reserved = self.initReserved()
		self.exp = P('exp')
		self.primary = P('primary') + ((token('(') + self.exp + token(')')) | num() | id(None,reserved) | words())
		self.factor = P('factor') + (id('-')+self.primary)|self.primary
		self.exp = self.exp + self.factor + OP(self.factor,optRules)
		self.statement = P('statement')
		self.block = P('block') + token('{') +self.statement.loop(True) + (  (token(';')|token('\n')) + self.statement.loop(True)  ).loop() +token('}')
		self.simple = P('simple') + ( self.exp )
		self.statement = self.statement + (  id('if') + self.exp + self.block + ( token('else') + self.block ).loop(True)  ) \
										| (  id('while') + self.exp + self.block  ) \
										| self.simple
		self.program = P('program') + self.statement.loop(True) + ( token(';')|token('\n') )
	def initReserved(self):
		reserved = [ ';' , '}' , '\n' ]
		return reserved
	def initOptRules(self):
		optRules = {}
		optRules['='] = (1,False)
		optRules['=='] = (2,True)
		optRules['>'] = (2,True)
		optRules['<'] = (2,True)
		optRules['+'] = (3,True)
		optRules['-'] = (3,True)
		optRules['*'] = (4,True)
		optRules['/'] = (4,True)
		optRules['%'] = (4,True)
		optRules['**'] = (5,False)
		return optRules
	def parse(self):
		ps = []
		self.program.parse(self.reader,ps)
		return ps

#  打印抽象语法树
def showAST(ast):
	import json
	result = json.dumps(ast,indent=4)
	print(result)
def showAST2(ast,lv=0):
	# print(ast)
	for t in ast:
		if not t:
			continue
		if type(t)!=list:
			print('- - '*lv+' '+str(t))
		else:
			showAST2(t,lv+1)

#  运行时环境对象
class Env(object):
	def __init__(self,name='',values={}):
		self.v = values
		self.outer= None
		self.name=name
		self.subId=0
	def setOuter(self,outerEnv):
		self.outer=outerEnv
	def get(self,key):
		env = self.where(key)
		return self.v[key] if env==self and key in self.v else None if env==self else env.get(key)
	def set(self,key,value):
		env = self.where(key)
		if env == self:
			self.v[key] = value
		elif env :
			env.set(key,value)
	def where(self,key):
		env = self if key in self.v else self.outer.where(key) if self.outer else None
		return env if env else self
	def sub(name=''):
		self.subId += 1
		vs = {}
		self.set('_%d_%s'%(self.subId,name),vs)
		return Env(name,vs)

#  脚本语言解释器
class LangureRunner(object):
	def __init__(self):
		self.evals = {}
		self.evals['program'] = self.programEval
		self.evals['exp'] = self.expEval
		self.evals['opt'] = self.optEval
		self.evals['demo'] = self.demo
		self.optInit()
	def run(self,ast,env=Env('runner')):
		# print('ast:',ast)
		k = self.evals[ast[0]]
		return k(ast,env)
	def programEval(self,ast,env):
		ast = ast[1]
		return self.run(ast,env)
	def expEval(self,ast,env):
		if len(ast) < 2:
			print('broken program ... exp broken ...',ast)
			return
		left = ast[1]
		optNum = 1
		while len(ast)>=optNum+2 :
			left = self.optEval(ast[optNum+1],left,env)
			optNum+=1
		return left
	def optInit(self):
		self.optSwitch = {
			"==":lambda x,y,env:x==y,
			">":lambda x,y,env:x>y,
			"<":lambda x,y,env:x<y,
			"+":lambda x,y,env:x+y,
			"-":lambda x,y,env:x-y,
			"*":lambda x,y,env:x*y,
			"/":lambda x,y,env:x/y,
			"%":lambda x,y,env:x%y,
			"**":lambda x,y,env:x**y,
		}
		self.vSwitch = {
			"=":lambda x,y,env:env.set(x,y),
		}
	def optEval(self,ast,left,env):
		if not left :
			return
		if type(left)!=float and type(left)!=str and len(left) > 1:
			left = left[1]
		opt = ast[1][2]
		right = ast[2]
		if right[0] != 'num':
			right = self.run(right)
		else:
			right = right[1]
		# print('pre right',right,ast[0],ast[1],len(ast))
		nextPos = 1
		while len(ast) >= 3+nextPos:
			right = self.optEval(ast[2+nextPos],right,env)
			nextPos += 1
		# print(opt,left,right)
		r = self.optSwitch[opt](float(left),float(right),env) if opt in self.optSwitch else self.vSwitch[opt](left,right,env)
		# print('r',r)
		return r
	def demo(self,h):
		print(h)

###############################################测试区#################################################

# 词法分析测试
def lexicaltest():
	# ts = ['"awef"','"ddsfe\"','ewfij','"eaf\\""','"ewafe\\awfeijie"','}}}}}}*&^%','32231',r'//afeieajojoiaefw']
	# reg = r'(\W)*'#r'"(\\"|\\\\|\\n|[^"])*"'
	# for t in ts:
	# 	print(t,re.match(reg,t).groups())
	# f = 'taskcenter.lua'
	f = 'store.st'
	r = []
	readLine(f,lexicalAnalysis,r)
	# r.append((-1,'EOF',''))
	print(r)

	reader = LexerReader(r)
	gr = ParserRules(reader).parse()
	showAST2(gr)
	
	# print(reader.read())

# 语法分析测试
def testParser():
	# t = '3+5*(4+3)*2/3' # 26.333333333333332
	# t = '123+234*(234-23423)*7/2' # -18991668.0
	t = 'a = 2*2**3**2+1' # 1025.0
	# t = 'sum = 0\ni = 0\n'
	# t = '(111)'
	# t = '1+1'
	lr = lexicalAnalysis(1,t)
	print(lr)
	r = LexerReader(lr)
	gr = ParserRules3(r).parse()
	showAST2(gr)
	env = Env('runner')
	r = LangureRunner().run(gr,env)
	print('>>>',r)
	print('>>>env:',env.v)

def testRunner():
	l = LangureRunner()
	dst = ['demo','hello,word']
	l.run(dst)

testParser()
