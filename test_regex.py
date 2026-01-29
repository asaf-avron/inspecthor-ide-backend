
import re

malformed_text = """
"text-syntax-keyword">trait SpecName {
  
  "text-syntax-keyword">method SayHello(buttonExists: "text-syntax-type">bool, helloMessageDisplayExists: "text-syntax-type">bool) "text-syntax-keyword">returns (new_helloMessageDisplayContent: "text-syntax-type">string, new_log: "text-syntax-type">map, new_errorAreaMessage: "text-syntax-type">string, new_errorAreaIsVisible: "text-syntax-type">bool)
    "text-syntax-keyword">requires buttonExists "text-syntax-keyword">class="text-syntax-comment">// [REF-05]
    "text-syntax-keyword">requires helloMessageDisplayExists "text-syntax-keyword">class="text-syntax-comment">// [REF-06]
    "text-syntax-keyword">ensures new_helloMessageDisplayContent == "Hello, World!" "text-syntax-keyword">class="text-syntax-comment">// [REF-07]
    "text-syntax-keyword">class="text-syntax-comment">// Missing implementation for error logging and error area updates (REF-08, REF-09, REF-10, REF-11)
"""

print("ORIGINAL:")
print(malformed_text)

# IMPROVED REGEX STRATEGY - TAKE 3

print("\n--- Testing Improved Strategy 3 ---\n")
cleaned = malformed_text

# 1. Remove attributes first! (class="...", style="...")
# Match word="anything"
cleaned = re.sub(r'\b[a-z-]+="[^"]*"', '', cleaned)

# 2. Remove orphaned tag endings like "text-syntax-keyword">
# This matches a quote, non-quotes, quote, greater-than
cleaned = re.sub(r'"[^"]*">', '', cleaned)

# 3. Remove standard tags
cleaned = re.sub(r'<[^>]*>', '', cleaned)

# 4. Remove any remaining angle brackets
cleaned = re.sub(r'[<>]', '', cleaned)


print("cleaned improved:")
print(cleaned)

if "class=" in cleaned:
    print("\nFAILED: class= still present")
elif "text-syntax-keyword" in cleaned:
    print("\nFAILED: text-syntax-keyword still present")
else:
    print("\nSUCCESS: All garbage truly removed")
