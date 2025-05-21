from enum import Enum, auto
from dataclasses import dataclass
import dataclasses
import re

class JsonTokenType(Enum):
    KEY = auto()
    STRING = auto()
    NUMBER = auto()
    BOOLEAN = auto()
    NULL = auto()
    LBRACE = auto()  # {
    RBRACE = auto()  # }
    LBRACKET = auto()  # [
    RBRACKET = auto()  # ]
    COLON = auto()   # :
    COMMA = auto()   # ,
    WHITESPACE = auto()
    ERROR = auto() # For syntax errors or unrecognized tokens

@dataclass
class Token:
    type: JsonTokenType
    value: str
    start_pos: int  # Absolute character offset from the beginning of the input string
    end_pos: int    # Absolute character offset (exclusive)
    line: int       # 1-indexed line number
    column: int     # 1-indexed column number (start of token on its line)

class JsonTokenizer:
    def __init__(self, json_string: str):
        self.json_string = json_string
        self.length = len(json_string)
        self.current_pos = 0
        self.current_line = 1
        self.current_col_offset = 0 # Tracks character offset from start of current_line

    def _create_token(self, token_type: JsonTokenType, value: str, start_pos: int, end_pos: int) -> Token:
        # Calculate line and column for the start_pos
        # This is a simplified calculation; a more robust one would re-scan from last newline
        # or maintain line start indices. For now, using current_line and relative col.
        
        # Find the start of the current line for accurate column calculation
        line_start_pos = self.json_string.rfind('\n', 0, start_pos) + 1
        
        token_line = self.json_string.count('\n', 0, start_pos) + 1
        token_column = start_pos - line_start_pos + 1
        
        return Token(type=token_type, value=value, start_pos=start_pos, end_pos=end_pos, line=token_line, column=token_column)

    def _post_process_tokens(self, tokens: list[Token]) -> list[Token]:
        processed_tokens: list[Token] = []
        i = 0
        while i < len(tokens):
            current_token = tokens[i]
            if current_token.type == JsonTokenType.STRING:
                # Look ahead for a COLON, skipping WHITESPACE
                j = i + 1
                while j < len(tokens) and tokens[j].type == JsonTokenType.WHITESPACE:
                    j += 1
                
                if j < len(tokens) and tokens[j].type == JsonTokenType.COLON:
                    # This string is a key
                    processed_tokens.append(dataclasses.replace(current_token, type=JsonTokenType.KEY))
                else:
                    processed_tokens.append(current_token)
            else:
                processed_tokens.append(current_token)
            i += 1
        return processed_tokens

    def tokenize(self) -> list[Token]:
        tokens_raw: list[Token] = []
        
        # Regex patterns (some from task details)
        # Order matters for matching: keywords before generic identifiers if any
        token_specification = [
            (JsonTokenType.WHITESPACE,  r'\s+'),                                # Whitespace
            (JsonTokenType.LBRACE,    r'\{'),                                  # {
            (JsonTokenType.RBRACE,    r'\}'),                                  # }
            (JsonTokenType.LBRACKET,  r'\['),                                  # [
            (JsonTokenType.RBRACKET,  r'\]'),                                  # ]
            (JsonTokenType.COLON,     r':'),                                   # :
            (JsonTokenType.COMMA,     r','),                                   # ,
            (JsonTokenType.NULL,      r'null\b'),                             # null
            (JsonTokenType.BOOLEAN,   r'true\b|false\b'),                     # true or false
            (JsonTokenType.STRING,    r'\"(?:\\\\.|[^\"\\\\])*\"'),        # String
            (JsonTokenType.NUMBER,    r'-?\\d+(?:\\.\\d+)?(?:[eE][+-]?\\d+)?'), # Number
            # KEY is not explicitly defined as a regex here because it's context-dependent (a string before a colon).
            # We will identify strings and then, in a later step or by context, determine if a STRING token is a KEY.
            # For now, all quoted sequences will be STRING tokens.
            (JsonTokenType.ERROR,     r'.')                                   # Any other character is an error
        ]
        
        # Combine regexes into one master regex
        tok_regex = '|'.join('(?P<%s>%s)' % (pair[0].name, pair[1]) for pair in token_specification)
        
        self.current_pos = 0
        while self.current_pos < self.length:
            match = re.match(tok_regex, self.json_string, self.current_pos)
            if match:
                token_type_name = match.lastgroup
                token_value = match.group(token_type_name)
                start_pos = self.current_pos
                self.current_pos = match.end()
                
                if token_type_name: # Should always be true if match is not None
                    token_type_enum = JsonTokenType[token_type_name]
                    # We will now include WHITESPACE tokens in the raw list 
                    # for the post-processor to use, but they can be filtered later if needed.
                    tokens_raw.append(self._create_token(token_type_enum, token_value, start_pos, self.current_pos))
            else:
                # This should not happen if ERROR regex is comprehensive ('.')
                # but as a fallback, create an error token for the problematic character
                tokens_raw.append(self._create_token(JsonTokenType.ERROR, self.json_string[self.current_pos], self.current_pos, self.current_pos + 1))
                self.current_pos += 1
                
        processed_tokens = self._post_process_tokens(tokens_raw)
        
        # Filter out WHITESPACE tokens from the final list if they are not needed for rendering
        final_tokens = [token for token in processed_tokens if token.type != JsonTokenType.WHITESPACE]
        
        return final_tokens

if __name__ == '__main__':
    # Example Usage:
    test_json_string = """
    {
        "name": "Test Object",
        "version": 1.23,
        "active": true,
        "description": null,
        "items": [ "item1", 100 ],
        "complex": { "nested_key": "nested_value" }
    }
    """
    tokenizer = JsonTokenizer(test_json_string)
    generated_tokens = tokenizer.tokenize()
    for token in generated_tokens:
        print(f"L{token.line:02d}C{token.column:02d} [{token.start_pos:03d}-{token.end_pos:03d}] {token.type.name:<10} : '{token.value}'")

    print("\n--- Test with an error ---")
    test_json_error_string = """{"key": value_not_string}"""
    tokenizer_error = JsonTokenizer(test_json_error_string)
    error_tokens = tokenizer_error.tokenize()
    for token in error_tokens:
        print(f"L{token.line:02d}C{token.column:02d} [{token.start_pos:03d}-{token.end_pos:03d}] {token.type.name:<10} : '{token.value}'")
        
    print("\n--- Test with mixed types and spacing ---")
    test_json_mixed = """
    [{"k":1},{"k": true  , "n":null}]
    """
    tokenizer_mixed = JsonTokenizer(test_json_mixed)
    mixed_tokens = tokenizer_mixed.tokenize()
    for token in mixed_tokens:
        print(f"L{token.line:02d}C{token.column:02d} [{token.start_pos:03d}-{token.end_pos:03d}] {token.type.name:<10} : '{token.value}'") 