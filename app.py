from flask import Flask, render_template, request, send_file
import dis
import io
import ast
import tokenize
import token
import contextlib
from io import BytesIO

app = Flask(__name__)

def generate_intermediate_code(node):
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
            return visit(node.value)

        elif isinstance(node, ast.Module):
            for stmt in node.body:
                visit(stmt)

        elif isinstance(node, ast.Call):
            args = [visit(arg) for arg in node.args]
            temp = get_temp()
            tac.append(f"{temp} = call {node.func.id}({', '.join(args)})")
            return temp

        elif isinstance(node, ast.For):
            iter_name = visit(node.target)
            iter_obj = visit(node.iter)
            tac.append(f"# For loop over {iter_obj}")
            start_label = f"L{temp_counter[0]}"
            temp_counter[0] += 1
            end_label = f"L{temp_counter[0]}"
            temp_counter[0] += 1

            tac.append(f"{start_label}:")
            tac.append(f"{iter_name} = next({iter_obj})  # pseudo")
            for stmt in node.body:
                visit(stmt)
            tac.append(f"goto {start_label}")
            tac.append(f"{end_label}:")
        else:
            tac.append(f"# Unsupported node: {type(node).__name__}")

    visit(node)
    return tac

def optimize_intermediate_code(tac_lines):
    optimized = []
    for line in tac_lines:
        note = ""
        if '=' in line and 'call' not in line:
            parts = line.split('=')
            var = parts[0].strip()
            expr = parts[1].strip()
            try:
                result = eval(expr, {"__builtins__": {}})
                line = f"{var} = {result}"
                note = "Constant folded"
            except:
                pass
        optimized.append((line, note))
    return optimized

def ast_to_html(node, indent=0):
    spacer = '&nbsp;' * 4 * indent
    if isinstance(node, ast.AST):
        fields = [(name, ast_to_html(value, indent + 1)) for name, value in ast.iter_fields(node)]
        children = ''.join(f"<div>{spacer}<strong>{type(node).__name__}.{name}</strong>: {value}</div>" for name, value in fields)
        return f"<div>{children}</div>"
    elif isinstance(node, list):
        return ''.join(ast_to_html(item, indent + 1) for item in node)
    else:
        return f"{spacer}{repr(node)}"

@app.route('/', methods=['GET', 'POST'])
def index():
    code = ''
    token_output = ''
    ast_output = ''
    ast_html_output = ''
    semantic_output = ''
    intermediate_code = []
    optimized_code = []
    bytecode_output = ''
    execution_output = ''

    if request.method == 'POST':
        code = request.form['code']
        try:
            # Lexical Analysis
            tokens = tokenize.tokenize(BytesIO(code.encode('utf-8')).readline)
            token_lines = []
            for tok in tokens:
                if tok.type == token.ENDMARKER:
                    continue
                token_lines.append(f"{token.tok_name[tok.type]:<15} {tok.string!r:>15}  (line {tok.start[0]}, column {tok.start[1]})")
            token_output = "\n".join(token_lines)

            # AST Generation
            parsed_ast = ast.parse(code)
            ast_output = ast.dump(parsed_ast, indent=4)
            ast_html_output = ast_to_html(parsed_ast)

            # Semantic Analysis
            try:
                compile(parsed_ast, filename="<ast>", mode="exec")
                semantic_output = "Semantic Analysis Passed ✅"
            except Exception as sem_error:
                semantic_output = f"Semantic Error ❌: {sem_error}"

            # Intermediate Code
            tac_lines = generate_intermediate_code(parsed_ast)
            intermediate_code = tac_lines

            # Optimization
            optimized_code = optimize_intermediate_code(tac_lines)

            # Bytecode
            code_obj = compile(code, '<string>', 'exec')
            instructions = list(dis.get_instructions(code_obj))
            detailed_bytecode = []
            for instr in instructions:
                line_info = f"{instr.starts_line or '':>4}"
                opcode = f"{instr.opname:<20}"
                arg = f"{instr.argrepr:<30}"
                comment = f"# {instr.argval}" if instr.argval is not None else ""
                detailed_bytecode.append(f"{line_info} {opcode} {arg} {comment}")
            bytecode_output = "\n".join(detailed_bytecode)

            # Execution
            exec_output_stream = io.StringIO()
            with contextlib.redirect_stdout(exec_output_stream):
                exec(code_obj, {})
            execution_output = exec_output_stream.getvalue()

        except Exception as e:
            execution_output = f"\U0001F4A5 Error during processing:\n{e.__class__.__name__}: {e}"

    return render_template('index.html',
                           code=code,
                           tokens=token_output,
                           ast_output=ast_output,
                           ast_html=ast_html_output,
                           semantic_output=semantic_output,
                           intermediate_code=intermediate_code,
                           optimized_code=optimized_code,
                           bytecode=bytecode_output,
                           output=execution_output)

@app.route('/download', methods=['POST'])
def download():
    code = request.form['code']
    bytecode = request.form['bytecode']
    content = f"Your Code:\n{code}\n\nBytecode:\n{bytecode}"
    buf = io.BytesIO()
    buf.write(content.encode())
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name='bytecode_output.txt')

if __name__ == '__main__':
    app.run(debug=True)