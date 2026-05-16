import com.github.javaparser.JavaParser;
import com.github.javaparser.ParseResult;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.ImportDeclaration;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.PackageDeclaration;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.ObjectCreationExpr;
import com.github.javaparser.ast.expr.MethodReferenceExpr;
import com.github.javaparser.ast.type.ClassOrInterfaceType;
import com.github.javaparser.ast.stmt.ForStmt;
import com.github.javaparser.ast.stmt.WhileStmt;
import com.github.javaparser.ast.stmt.DoStmt;
import com.github.javaparser.ast.stmt.ForEachStmt;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * JavaParser Bridge Tool
 * Output AST info as JSON via command line
 */
public class JavaParserBridge {
    
    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("Usage: java JavaParserBridge <java_source_code>");
            System.exit(1);
        }
        
        // Read Java code from command line args or stdin
        String javaCode;
        if ("--stdin".equals(args[0])) {
            // Read from stdin
            try {
                javaCode = readStdin();
            } catch (IOException e) {
                System.err.println("Error reading from stdin: " + e.getMessage());
                System.exit(1);
                return;
            }
        } else {
            // Read from args
            javaCode = args[0];
        }
        
        // Parse Java code
        JavaParser parser = new JavaParser();
        ParseResult<CompilationUnit> result = parser.parse(javaCode);
        
        if (!result.isSuccessful() || !result.getResult().isPresent()) {
            // Parse failed, output error
            Map<String, Object> error = new HashMap<String, Object>();
            error.put("success", false);
            error.put("error", "Parse error");
            if (result.getProblems().size() > 0) {
                error.put("message", result.getProblems().get(0).getMessage());
            }
            System.out.println(toJson(error));
            System.exit(0);
        }
        
        CompilationUnit cu = result.getResult().get();
        
        // Extract AST info
        Map<String, Object> astInfo = extractAstInfo(cu);
        astInfo.put("success", true);
        
        // Output JSON
        System.out.println(toJson(astInfo));
    }
    
    private static String readStdin() throws IOException {
        StringBuilder sb = new StringBuilder();
        byte[] buffer = new byte[1024];
        int n;
        while ((n = System.in.read(buffer)) != -1) {
            sb.append(new String(buffer, 0, n, StandardCharsets.UTF_8));
        }
        return sb.toString();
    }
    
    /**
     * Check if a node is inside a loop (for, while, do-while, for-each)
     */
    private static boolean isInsideLoop(Node node) {
        Node parent = node.getParentNode().orElse(null);
        while (parent != null) {
            if (parent instanceof ForStmt || 
                parent instanceof WhileStmt || 
                parent instanceof DoStmt ||
                parent instanceof ForEachStmt) {
                return true;
            }
            parent = parent.getParentNode().orElse(null);
        }
        return false;
    }
    
    /**
     * Extract AST key information
     */
    private static Map<String, Object> extractAstInfo(CompilationUnit cu) {
        Map<String, Object> info = new HashMap<String, Object>();
            
        // Package declaration
        Optional<PackageDeclaration> pkg = cu.getPackageDeclaration();
        if (pkg.isPresent()) {
            info.put("package", pkg.get().getNameAsString());
        }
            
        // Import statements
        List<Map<String, Object>> imports = new ArrayList<Map<String, Object>>();
        for (ImportDeclaration imp : cu.getImports()) {
            Map<String, Object> impInfo = new HashMap<String, Object>();
            impInfo.put("path", imp.getNameAsString());
            impInfo.put("static", imp.isStatic());
            impInfo.put("wildcard", imp.isAsterisk());
            impInfo.put("line", imp.getBegin().isPresent() ? imp.getBegin().get().line : 0);
            imports.add(impInfo);
        }
        info.put("imports", imports);
            
        // Type declarations (classes, interfaces)
        List<Map<String, Object>> types = new ArrayList<Map<String, Object>>();
        for (ClassOrInterfaceDeclaration type : cu.findAll(ClassOrInterfaceDeclaration.class)) {
            Map<String, Object> typeInfo = new HashMap<String, Object>();
            typeInfo.put("name", type.getNameAsString());
            typeInfo.put("interface", type.isInterface());
            typeInfo.put("line", type.getBegin().isPresent() ? type.getBegin().get().line : 0);
                
            // Extends
            if (type.getExtendedTypes().size() > 0) {
                List<String> extendsList = new ArrayList<String>();
                for (ClassOrInterfaceType ext : type.getExtendedTypes()) {
                    extendsList.add(ext.getNameAsString());
                }
                typeInfo.put("extends", extendsList);
            }
                
            // Implements
            if (type.getImplementedTypes().size() > 0) {
                List<String> implementsList = new ArrayList<String>();
                for (ClassOrInterfaceType impl : type.getImplementedTypes()) {
                    implementsList.add(impl.getNameAsString());
                }
                typeInfo.put("implements", implementsList);
            }
                
            // Fields
            List<Map<String, Object>> fields = new ArrayList<Map<String, Object>>();
            for (FieldDeclaration field : type.findAll(FieldDeclaration.class)) {
                Map<String, Object> fieldInfo = new HashMap<String, Object>();
                fieldInfo.put("type", field.getElementType().asString());
                fieldInfo.put("line", field.getBegin().isPresent() ? field.getBegin().get().line : 0);
                
                // 提取字段修饰符（static, final, private, public 等）
                List<String> modifiers = new ArrayList<String>();
                for (com.github.javaparser.ast.Modifier mod : field.getModifiers()) {
                    modifiers.add(mod.getKeyword().asString());
                }
                fieldInfo.put("modifiers", modifiers);
                
                // 提取变量声明符（变量名）
                List<Map<String, Object>> declarators = new ArrayList<Map<String, Object>>();
                for (com.github.javaparser.ast.body.VariableDeclarator vd : field.getVariables()) {
                    Map<String, Object> declInfo = new HashMap<String, Object>();
                    declInfo.put("name", vd.getNameAsString());
                    declarators.add(declInfo);
                }
                fieldInfo.put("declarators", declarators);
                
                fields.add(fieldInfo);
            }
            typeInfo.put("fields", fields);
                
            // Methods
            List<Map<String, Object>> methods = new ArrayList<Map<String, Object>>();
            for (MethodDeclaration method : type.findAll(MethodDeclaration.class)) {
                Map<String, Object> methodInfo = new HashMap<String, Object>();
                methodInfo.put("name", method.getNameAsString());
                methodInfo.put("line", method.getBegin().isPresent() ? method.getBegin().get().line : 0);
                    
                // Return type
                if (method.getType() != null) {
                    methodInfo.put("returnType", method.getType().asString());
                }
                    
                // Parameters
                List<Map<String, Object>> params = new ArrayList<Map<String, Object>>();
                for (com.github.javaparser.ast.body.Parameter param : method.getParameters()) {
                    Map<String, Object> paramInfo = new HashMap<String, Object>();
                    paramInfo.put("name", param.getNameAsString());
                    paramInfo.put("type", param.getType().asString());
                    params.add(paramInfo);
                }
                methodInfo.put("parameters", params);

                // Method calls inside this method
                List<Map<String, Object>> methodCalls = new ArrayList<Map<String, Object>>();
                if (method.getBody().isPresent()) {
                    for (MethodCallExpr call : method.getBody().get().findAll(MethodCallExpr.class)) {
                        Map<String, Object> callInfo = new HashMap<String, Object>();
                        callInfo.put("name", call.getNameAsString());
                        if (call.getScope().isPresent()) {
                            callInfo.put("scope", call.getScope().get().toString());
                        }
                        callInfo.put("line", call.getBegin().isPresent() ? call.getBegin().get().line : 0);
                        // Check if this call is inside a loop
                        callInfo.put("inLoop", isInsideLoop(call));
                        methodCalls.add(callInfo);
                    }
                    
                    // Also collect method references (e.g., Class::method)
                    for (MethodReferenceExpr ref : method.getBody().get().findAll(MethodReferenceExpr.class)) {
                        Map<String, Object> refInfo = new HashMap<String, Object>();
                        refInfo.put("name", ref.getIdentifier());
                        refInfo.put("scope", ref.getScope().toString());
                        refInfo.put("line", ref.getBegin().isPresent() ? ref.getBegin().get().line : 0);
                        refInfo.put("inLoop", isInsideLoop(ref));
                        refInfo.put("isMethodReference", true);
                        methodCalls.add(refInfo);
                    }
                }
                methodInfo.put("methodCalls", methodCalls);
                    
                methods.add(methodInfo);
            }
            typeInfo.put("methods", methods);
                
            // Constructors
            List<Map<String, Object>> constructors = new ArrayList<Map<String, Object>>();
            for (ConstructorDeclaration ctor : type.findAll(ConstructorDeclaration.class)) {
                Map<String, Object> ctorInfo = new HashMap<String, Object>();
                ctorInfo.put("line", ctor.getBegin().isPresent() ? ctor.getBegin().get().line : 0);
                    
                List<Map<String, Object>> params = new ArrayList<Map<String, Object>>();
                for (com.github.javaparser.ast.body.Parameter param : ctor.getParameters()) {
                    Map<String, Object> paramInfo = new HashMap<String, Object>();
                    paramInfo.put("name", param.getNameAsString());
                    paramInfo.put("type", param.getType().asString());
                    params.add(paramInfo);
                }
                ctorInfo.put("parameters", params);
                    
                constructors.add(ctorInfo);
            }
            typeInfo.put("constructors", constructors);
                
            // Method calls at class level (only those not inside methods)
            // Note: Method calls inside methods are already captured in methodInfo
            List<Map<String, Object>> methodCalls = new ArrayList<Map<String, Object>>();
            typeInfo.put("methodCalls", methodCalls);
                
            // Object creations
            List<Map<String, Object>> objectCreations = new ArrayList<Map<String, Object>>();
            for (ObjectCreationExpr creation : type.findAll(ObjectCreationExpr.class)) {
                Map<String, Object> creationInfo = new HashMap<String, Object>();
                creationInfo.put("type", creation.getType().getNameAsString());
                creationInfo.put("line", creation.getBegin().isPresent() ? creation.getBegin().get().line : 0);
                objectCreations.add(creationInfo);
            }
            typeInfo.put("objectCreations", objectCreations);
                
            types.add(typeInfo);
        }
        info.put("types", types);
            
        return info;
    }
    
    /**
     * Simple JSON serialization
     */
    private static String toJson(Object obj) {
        StringBuilder sb = new StringBuilder();
        toJson(obj, sb);
        return sb.toString();
    }
    
    @SuppressWarnings("unchecked")
    private static void toJson(Object obj, StringBuilder sb) {
        if (obj == null) {
            sb.append("null");
        } else if (obj instanceof String) {
            sb.append("\"").append(escapeJson((String) obj)).append("\"");
        } else if (obj instanceof Number || obj instanceof Boolean) {
            sb.append(obj.toString());
        } else if (obj instanceof List) {
            sb.append("[");
            List<?> list = (List<?>) obj;
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) sb.append(",");
                toJson(list.get(i), sb);
            }
            sb.append("]");
        } else if (obj instanceof Map) {
            sb.append("{");
            Map<?, ?> map = (Map<?, ?>) obj;
            boolean first = true;
            for (Map.Entry<?, ?> entry : map.entrySet()) {
                if (!first) sb.append(",");
                first = false;
                sb.append("\"").append(entry.getKey()).append("\":");
                toJson(entry.getValue(), sb);
            }
            sb.append("}");
        }
    }
    
    private static String escapeJson(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\")
                .replace("\"", "\\\"")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
