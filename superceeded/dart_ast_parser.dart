// dart_ast_parser.dart (V6.1 - Linter Cleanups)
import 'dart:io';
import 'dart:convert';
import 'package:analyzer/dart/analysis/features.dart';
import 'package:analyzer/dart/analysis/utilities.dart';
import 'package:analyzer/dart/ast/ast.dart';
import 'package:analyzer/dart/ast/visitor.dart';
import 'package:analyzer/dart/element/element.dart';
// Removed: import 'package:analyzer/dart/ast/token.dart'; // Unused

void main(List<String> arguments) {
  // ... (main function remains the same) ...
  if (arguments.isEmpty) {
    stderr.writeln('Error: No Dart file path provided.');
    exit(1);
  }
  final filePath = arguments[0];
  final file = File(filePath);

  if (!file.existsSync()) {
    stderr.writeln('Error: File not found at $filePath');
    exit(1);
  }

  try {
    final content = file.readAsStringSync();
    final parseResult = parseString(
      content: content,
      featureSet: FeatureSet.latestLanguageVersion(),
      throwIfDiagnostics: false,
    );

    final compilationUnit = parseResult.unit;
    final visitor = CodeElementVisitor(content);
    compilationUnit.visitChildren(visitor);

    for (final elementData in visitor.elements) {
      print(jsonEncode(elementData));
    }
    if (visitor.elements.isEmpty && content.trim().isNotEmpty) {
      stderr.writeln(
          'DEBUG_WARN: No elements were extracted by the visitor for non-empty file: $filePath');
    }
  } catch (e, s) {
    stderr.writeln('Error processing file $filePath: $e');
    stderr.writeln('Stack trace:\n$s');
    exit(1);
  }
}

class CodeElementVisitor extends GeneralizingAstVisitor<void> {
  final String sourceContent;
  final List<Map<String, dynamic>> elements = [];

  CodeElementVisitor(this.sourceContent);

  String _getSourceText(int startOffset, int endOffset) {
    final safeStart = startOffset.clamp(0, sourceContent.length);
    final safeEnd = endOffset.clamp(0, sourceContent.length);
    return (safeStart < safeEnd)
        ? sourceContent.substring(safeStart, safeEnd)
        : "";
  }

  String _cleanDocComment(String? rawDoc) {
    // ... (cleanDocComment remains the same) ...
    if (rawDoc == null || rawDoc.isEmpty) return '';
    var lines = rawDoc.split('\n');
    var cleanedLines = <String>[];
    bool inCodeBlock = false;
    for (var line in lines) {
      var trimmedLine = line.trim();
      if (trimmedLine.startsWith('```')) inCodeBlock = !inCodeBlock;
      if (inCodeBlock) {
        cleanedLines.add(line);
        continue;
      }
      if (trimmedLine.startsWith('///'))
        cleanedLines.add(trimmedLine.substring(3).trimLeft());
      else if (trimmedLine.startsWith('/**'))
        cleanedLines.add(trimmedLine.substring(3).trimLeft());
      else if (trimmedLine.endsWith('*/'))
        cleanedLines
            .add(trimmedLine.substring(0, trimmedLine.length - 2).trimRight());
      else if (trimmedLine.startsWith('*') && cleanedLines.isNotEmpty)
        cleanedLines.add(trimmedLine.substring(1).trimLeft());
      else if (cleanedLines.isNotEmpty &&
          !trimmedLine.startsWith('/**') &&
          !trimmedLine.startsWith('///')) cleanedLines.add(trimmedLine);
    }
    return cleanedLines.join('\n').trim();
  }

  String _extractFullDocComments(Declaration nodeWithDocs) {
    // nodeWithDocs is Declaration (extends AnnotatedNode)
    final element = nodeWithDocs.declaredElement;
    if (element != null &&
        element.documentationComment != null &&
        element.documentationComment!.isNotEmpty) {
      return _cleanDocComment(element.documentationComment);
    }

    // nodeWithDocs is already an AnnotatedNode, so no need for 'is AnnotatedNode' check
    Comment? astComment = nodeWithDocs.documentationComment;
    if (astComment != null) {
      // 'isDocumentation' is deprecated and always true for Comment nodes from documentationComment
      return _cleanDocComment(
          astComment.tokens.map((t) => t.lexeme).join('\n'));
    }
    return '';
  }

  int _getStartOffsetWithDocs(Declaration node) {
    // node is Declaration (extends AnnotatedNode)
    int effectiveOffset = node.offset;

    // node is already an AnnotatedNode
    Comment? docComment = node.documentationComment;
    List<Annotation> annotations = node.metadata;

    if (docComment != null) {
      effectiveOffset = docComment.offset;
    } else if (annotations.isNotEmpty) {
      effectiveOffset = annotations.first.offset;
    }
    return effectiveOffset;
  }

  void _addElement(String type, String name, Declaration node,
      {AstNode? bodyNodeForEndOffset}) {
    // ... (_addElement remains the same) ...
    int startOffset = _getStartOffsetWithDocs(node);
    int endOffset = (bodyNodeForEndOffset ?? node).end;
    String codeBlock = _getSourceText(startOffset, endOffset);
    String docCommentText = _extractFullDocComments(node);
    int lineCount = codeBlock.split('\n').length;

    if (codeBlock.trim().isEmpty) return;
    if (lineCount < 1 &&
        !['field', 'top_level_variable', 'enum_constant'].contains(type)) {
      return;
    }

    elements.add({
      'element_type': type,
      'element_name': name,
      'code_block': codeBlock.trim(),
      'doc_comment': docCommentText,
      'start_line': _getLineNumber(startOffset),
      'end_line': _getLineNumber(endOffset - 1),
    });
  }

  int _getLineNumber(int offset) {
    // ... (remains the same) ...
    if (offset < 0) return 1;
    offset = offset.clamp(0, sourceContent.length);
    return sourceContent.substring(0, offset).split('\n').length;
  }

  // --- Visitor Methods ---
  @override
  void visitClassDeclaration(ClassDeclaration node) {
    // ... (remains the same) ...
    _addElement('class', node.name.lexeme, node);
    node.members.forEach((member) => member.accept(this));
  }

  @override
  void visitMixinDeclaration(MixinDeclaration node) {
    // ... (remains the same) ...
    _addElement('mixin', node.name.lexeme, node);
    node.members.forEach((member) => member.accept(this));
  }

  @override
  void visitEnumDeclaration(EnumDeclaration node) {
    // ... (remains the same) ...
    final element = node.declaredElement;
    if (element != null) {
      // Use element name if available
      _addElement('enum', element.name, node);
      for (var constant in node.constants) {
        final constantElement = constant.declaredElement;
        if (constantElement != null) {
          _addElement('enum_constant',
              '${element.name}.${constantElement.name}', constant);
        } else {
          _addElement('enum_constant_ast',
              '${element.name}.${constant.name.lexeme}', constant);
        }
      }
    } else {
      // Fallback if main enum element is null
      _addElement('enum', node.name.lexeme, node);
      for (var constant in node.constants) {
        _addElement('enum_constant_ast',
            '${node.name.lexeme}.${constant.name.lexeme}', constant);
      }
    }
    node.members.forEach((member) => member.accept(this));
  }

  @override
  void visitExtensionDeclaration(ExtensionDeclaration node) {
    // ExtensionDeclaration.name *is* nullable. Keep ?. for safety.
    // ignore: invalid_null_aware_operator_on_nullable_type
    // (Only if linter still complains and you are sure it's a false positive for this specific AST property)
    // For now, let's assume the linter might be right about the specific context it sees.
    // If node.name can truly not be null here based on how it's reached, then node.name.lexeme is fine.
    // However, AST definition for ExtensionDeclaration.name is SimpleIdentifier? (nullable).
    // So, using ?. is safer. If the linter insists, it might be confused.
    _addElement('extension', node.name?.lexeme ?? 'UnnamedExtension', node);
    node.members.forEach((member) => member.accept(this));
  }

  @override
  void visitExtensionTypeDeclaration(ExtensionTypeDeclaration node) {
    // ExtensionTypeDeclaration.name is NON-nullable (SimpleIdentifier name).
    // So, node.name.lexeme is correct. The linter warning for this would be valid to fix to '.'.
    _addElement(
        'extension_type', node.name.lexeme, node); // Should be node.name.lexeme
    node.members.forEach((member) => member.accept(this));
  }

  @override
  void visitFunctionDeclaration(FunctionDeclaration node) {
    // ... (remains the same) ...
    String functionName = node.name.lexeme;
    String type = 'function';
    if (node.isGetter)
      type = 'top_level_getter';
    else if (node.isSetter) type = 'top_level_setter';

    _addElement(type, functionName, node,
        bodyNodeForEndOffset: node.functionExpression.body);
  }

  @override
  void visitMethodDeclaration(MethodDeclaration node) {
    // ... (remains the same as V6) ...
    final ExecutableElement? element = node.declaredElement;

    if (element == null) {
      String fallbackName = node.name?.lexeme ?? "unknown_method_constructor";
      String astBasedType = "method_ast_fallback";
      if (node.returnType == null && node.name?.lexeme != null) {
        astBasedType = "constructor_ast_fallback";
      }
      _addElement(astBasedType, fallbackName, node,
          bodyNodeForEndOffset: node.body);
      return;
    }

    String elementName = element.displayName;
    String elementType = 'method';

    if (element is ConstructorElement) {
      elementType = 'constructor';
      elementName = element.displayName;
    } else if (element is PropertyAccessorElement) {
      if (element.kind == ElementKind.GETTER) {
        elementType = 'getter';
      } else if (element.kind == ElementKind.SETTER) {
        elementType = 'setter';
      }
    } else if (element is MethodElement) {
      if (node.isOperator) {
        elementType = 'operator';
      }
    }

    _addElement(elementType, elementName, node,
        bodyNodeForEndOffset: node.body);
  }

  @override
  void visitTopLevelVariableDeclaration(TopLevelVariableDeclaration node) {
    // ... (remains the same) ...
    for (var variable in node.variables.variables) {
      final element = variable.declaredElement;
      if (element is TopLevelVariableElement) {
        _addElement('top_level_variable', element.name, node);
      } else {
        _addElement('top_level_variable_ast', variable.name.lexeme, node);
      }
    }
  }

  @override
  void visitFieldDeclaration(FieldDeclaration node) {
    // ... (remains the same) ...
    for (var variable in node.fields.variables) {
      final element = variable.declaredElement;
      if (element is FieldElement) {
        _addElement('field', element.name, node);
      } else {
        _addElement('field_ast', variable.name.lexeme, node);
      }
    }
  }
}
