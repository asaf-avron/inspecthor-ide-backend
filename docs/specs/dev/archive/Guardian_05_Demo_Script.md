# **Guardian Gateway: Hackathon Demo Script**

## **Opening Hook (0:00 \- 0:20)**

* **Speaker:** "We all use AI agents to write code. But let's be honest: Do you trust them? If an AI writes a banking transfer function, do you trust it not to lose money?"  
* **Action:** Show a slide: "Code Generation is Solved. Code Verification is the new frontier."  
* **Pitch:** "Meet Guardian Gateway. The first autonomous infrastructure that polices your AI agents using Formal Verification."

## **The "Ambiguity Hunt" (0:20 \- 0:50)**

* **Speaker:** "It starts with the Spec. Here is a simple English requirement for a Rewards System."  
* **Action:** Paste test\_spec.md into the **Spec Auditor UI**.  
* **Speaker:** "It looks fine to a human. But let's ask the Guardian."  
* **Action:** Click **Verify**. Show the **RED GAP CARDS**.  
* **Speaker:** "Boom. In 3 seconds, it found a 'Negative Money' exploit and a 'Database Race Condition' that we missed. It generates a mathematically precise Dafny contract to fix this."

## **The "Verification & Fix" (0:50 \- 1:30)**

* **Speaker:** "Now, let's try to deploy code. Our Junior Agent submits a PR."  
* **Action:** Switch to **Mission Control UI**. Show the "Incoming Code" with a bug.  
* **Speaker:** "The Guardian intercepts it. It doesn't just read the code; it *compiles* it against the Math Contract."  
* **Action:** Show the "Thinking" spinner \-\> **RED ALERT** (Compiler Error).  
* **Speaker:** "Blocked. The compiler proved the logic was flawed. But Guardian doesn't just complain—it fixes."  
* **Action:** Show the "Self-Healing" animation \-\> **GREEN SUCCESS**.

## **Closing (1:30 \- 2:00)**

* **Speaker:** "We leveraged Gemini 3's Thinking Mode to lower the barrier of entry to Formal Methods. We are bringing 'NASA-grade' security to every enterprise Python developer."  
* **Action:** Show the "Cryptographically Signed" badge.  
* **Tagline:** "Don't just generate code. Verify it. Guardian Gateway."