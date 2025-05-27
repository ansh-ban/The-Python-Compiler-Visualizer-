from flask import Flask, request, jsonify, render_template
import ast
import dis
import io
import token
import tokenize
import contextlib

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

def get_ast_tree(code):
    return ast.parse(code)

def generate_tac(node):
    temp_counter = [0]
    tac = []

    def get_temp():
        temp = f"t{temp_counter[0]}"
        temp_counter[0] += 1
        return temp

    def visit(node):
        if isinstance(node, ast.BinOp):
            left = visit(node.left)
            right = visit(node.right)
            temp = get_temp()
            op = type(node.op).__name__
            tac.append(f"{temp} = {left} {op} {right}")
            return temp

        elif isinstance(node, ast.Constant):
            return str(node.value)

        elif isinstance(node, ast.Name):
            return node.id

        elif isinstance(node, ast.Assign):
            val = visit(node.value)
            for target in node.targets:
                tac.append(f"{target.id} = {val}")

        elif isinstance(node, ast.Expr):
            visit(node.value)

        elif isinstance(node, ast.Call):
            args = [visit(arg) for arg in node.args]
            temp = get_temp()
            func_name = node.func.id if isinstance(node.func, ast.Name) else str(node.func)
            tac.append(f"{temp} = call {func_name}({', '.join(args)})")
            return temp

        elif isinstance(node, ast.For):
            target = visit(node.target)
            iter_ = visit(node.iter)
            tac.append(f"# for {target} in {iter_}")
            for stmt in node.body:
                visit(stmt)
            tac.append("# end for")

        elif isinstance(node, ast.If):
            cond = visit(node.test)
            label_false = f"L{temp_counter[0]}"
            temp_counter[0] += 1
            label_end = f"L{temp_counter[0]}"
            temp_counter[0] += 1
            tac.append(f"if not {cond} goto {label_false}")
            for stmt in node.body:
                visit(stmt)
            tac.append(f"goto {label_end}")
            tac.append(f"{label_false}:")
            for stmt in node.orelse:
                visit(stmt)
            tac.append(f"{label_end}:")

        elif isinstance(node, ast.Module):
            for stmt in node.body:
                visit(stmt)

        else:
            tac.append(f"# Unsupported: {type(node).__name__}")

    visit(node)
    return tac

@app.route('/execute', methods=['POST'])
def execute_code():
    code = request.json.get('code', '')
    try:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(code, {})
        return jsonify({"output": output.getvalue()})
    except Exception as e:
        return jsonify({"output": f"{e.__class__.__name__}: {e}"}), 400

@app.route('/lexical', methods=['POST'])
def lexical_analysis():
    code = request.json.get('code', '')
    try:
        tokens = tokenize.tokenize(io.BytesIO(code.encode('utf-8')).readline)
        result = []
        for tok in tokens:
            if tok.type != token.ENDMARKER:
                result.append(f"{token.tok_name[tok.type]:<12} {tok.string!r:>10}  (line {tok.start[0]}, col {tok.start[1]})")
        return jsonify({"output": result})
    except Exception as e:
        return jsonify({"output": [f"{e.__class__.__name__}: {e}"]}), 400

@app.route('/ast', methods=['POST'])
def syntax_analysis():
    code = request.json.get('code', '')
    try:
        tree = get_ast_tree(code)
        return jsonify({"output": ast.dump(tree, indent=4)})
    except Exception as e:
        return jsonify({"output": f"{e.__class__.__name__}: {e}"}), 400

@app.route('/semantic', methods=['POST'])
def semantic_analysis():
    code = request.json.get('code', '')
    try:
        tree = get_ast_tree(code)
        compile(tree, '<string>', 'exec')  # semantic check
        return jsonify({"output": "Semantic Analysis Passed ✅"})
    except Exception as e:
        return jsonify({"output": f"{e.__class__.__name__}: {e}"}), 400

@app.route('/tac', methods=['POST'])
def intermediate_code():
    code = request.json.get('code', '')
    try:
        tree = get_ast_tree(code)
        tac = generate_tac(tree)
        return jsonify({"output": tac})
    except Exception as e:
        return jsonify({"output": [f"{e.__class__.__name__}: {e}"]}), 400

@app.route('/bytecode', methods=['POST'])
def bytecode():
    code = request.json.get('code', '')
    try:
        code_obj = compile(code, '<string>', 'exec')
        output = []
        for instr in dis.get_instructions(code_obj):
            output.append(f"{instr.offset:>3} {instr.opname:<20} {instr.argrepr}")
        return jsonify({"output": output})
    except Exception as e:
        return jsonify({"output": [f"{e.__class__.__name__}: {e}"]}), 400

def optimize_ast(node):
    class ConstantFolder(ast.NodeTransformer):
        def visit_BinOp(self, node):
            self.generic_visit(node)
            if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
                try:
                    value = eval(compile(ast.Expression(node), '', 'eval'))
                    return ast.Constant(value=value)
                except:
                    pass
            return node

        def visit_If(self, node):
            self.generic_visit(node)
            if isinstance(node.test, ast.Constant):
                if node.test.value:
                    return node.body  # return the body (list of nodes)
                else:
                    return node.orelse
            return node

    optimized = ConstantFolder().visit(node)
    if isinstance(optimized, list):
        optimized = ast.Module(body=optimized, type_ignores=[])
    ast.fix_missing_locations(optimized)
    return optimized

@app.route('/optimize', methods=['POST'])
def optimize_code():
    code = request.json.get('code', '')
    try:
        tree = ast.parse(code)
        optimized_tree = optimize_ast(tree)
        optimized_code = ast.unparse(optimized_tree)
        return jsonify({"output": optimized_code})
    except Exception as e:
        return jsonify({"output": f"{e.__class__.__name__}: {e}"}), 400

if __name__ == '__main__':
    app.run(debug=True)
