# Dafny Domain Prelude Library Specification

> **Phase:** 2 - The Bridge (Supporting Infrastructure)  
> **Priority:** P2 - Enables domain-specific verification  
> **Estimated Effort:** 1 sprint

---

## 1. Logic Model (State)

### Entities
- **PreludeModule** - Reusable Dafny module for specific domain
- **TypeDefinition** - Domain-specific types (Currency, AccountId, etc.)
- **TraitContract** - Abstract interface for domain operations
- **LemmaLibrary** - Pre-proven lemmas for common patterns

### Domains Covered
1. **Banking** - Currency, accounts, transfers, ledgers
2. **Healthcare** - Patients, records, consent, HIPAA constraints
3. **Authentication** - Sessions, tokens, permissions

---

## 2. Banking Prelude Module

### File: `preludes/banking.dfy`

```dafny
module Banking {
    // === Types ===
    type Currency = real
    type AccountId = string
    
    // === Predicates ===
    predicate ValidAmount(amount: Currency) {
        amount >= 0.0
    }
    
    predicate ValidAccountId(id: AccountId) {
        |id| > 0 && |id| <= 64
    }
    
    // === Account Class ===
    class Account {
        var balance: Currency
        var is_active: bool
        ghost var history: seq<Transaction>
        
        predicate Valid() reads this {
            balance >= 0.0
        }
        
        constructor(initial_balance: Currency)
            requires ValidAmount(initial_balance)
            ensures Valid()
            ensures balance == initial_balance
            ensures is_active == true
        {
            balance := initial_balance;
            is_active := true;
            history := [];
        }
        
        method Deposit(amount: Currency)
            requires Valid()
            requires ValidAmount(amount)
            requires is_active
            modifies this
            ensures Valid()
            ensures balance == old(balance) + amount
        {
            balance := balance + amount;
        }
        
        method Withdraw(amount: Currency) returns (success: bool)
            requires Valid()
            requires ValidAmount(amount)
            requires is_active
            modifies this
            ensures Valid()
            ensures success ==> balance == old(balance) - amount
            ensures !success ==> balance == old(balance)
            ensures success <==> old(balance) >= amount
        {
            if balance >= amount {
                balance := balance - amount;
                success := true;
            } else {
                success := false;
            }
        }
    }
    
    // === Transfer Trait ===
    trait TransferInterface {
        method Transfer(from: Account, to: Account, amount: Currency) 
            returns (success: bool)
            requires from.Valid() && to.Valid()
            requires ValidAmount(amount) && amount > 0.0
            requires from != to
            requires from.is_active && to.is_active
            modifies from, to
            ensures from.Valid() && to.Valid()
            ensures success ==> from.balance == old(from.balance) - amount
            ensures success ==> to.balance == old(to.balance) + amount
            ensures !success ==> from.balance == old(from.balance)
            ensures !success ==> to.balance == old(to.balance)
            // Conservation of money
            ensures from.balance + to.balance == old(from.balance) + old(to.balance)
    }
    
    // === Lemmas ===
    lemma ConservationOfMoney(before_from: Currency, before_to: Currency,
                               after_from: Currency, after_to: Currency,
                               amount: Currency)
        requires before_from >= amount
        requires after_from == before_from - amount
        requires after_to == before_to + amount
        ensures after_from + after_to == before_from + before_to
    {
        // Proof is automatic
    }
}
```

---

## 3. Healthcare Prelude Module

### File: `preludes/healthcare.dfy`

```dafny
module Healthcare {
    // === Types ===
    type PatientId = string
    type ProviderId = string
    type RecordId = string
    type Timestamp = int
    
    datatype ConsentLevel = 
        | NoConsent
        | ReadOnly
        | ReadWrite
        | Emergency
    
    datatype RecordType =
        | Diagnosis
        | Medication
        | LabResult
        | Procedure
    
    // === Predicates ===
    predicate ValidPatientId(id: PatientId) {
        |id| > 0 && |id| <= 32
    }
    
    predicate HasConsent(consent: ConsentLevel, required: ConsentLevel) {
        match required {
            case NoConsent => true
            case ReadOnly => consent in {ReadOnly, ReadWrite, Emergency}
            case ReadWrite => consent in {ReadWrite, Emergency}
            case Emergency => consent == Emergency
        }
    }
    
    // === Medical Record ===
    class MedicalRecord {
        var patient_id: PatientId
        var record_type: RecordType
        var content: string
        var created_at: Timestamp
        var created_by: ProviderId
        ghost var access_log: seq<(ProviderId, Timestamp)>
        
        predicate Valid() reads this {
            ValidPatientId(patient_id) &&
            created_at > 0 &&
            |created_by| > 0
        }
    }
    
    // === Access Control Trait ===
    trait HIPAACompliant {
        method AccessRecord(provider: ProviderId, record: MedicalRecord,
                           consent: ConsentLevel)
            returns (content: string, allowed: bool)
            requires record.Valid()
            modifies record
            ensures allowed ==> HasConsent(consent, ReadOnly)
            ensures allowed ==> content == record.content
            ensures !allowed ==> content == ""
            // Audit trail requirement
            ensures |record.access_log| == |old(record.access_log)| + 1
    }
}
```

---

## 4. Authentication Prelude Module

### File: `preludes/authentication.dfy`

```dafny
module Authentication {
    // === Types ===
    type UserId = string
    type TokenId = string
    type PermissionSet = set<string>
    type Timestamp = int
    
    // === Token ===
    class SessionToken {
        var token_id: TokenId
        var user_id: UserId
        var permissions: PermissionSet
        var issued_at: Timestamp
        var expires_at: Timestamp
        var revoked: bool
        
        predicate Valid() reads this {
            |token_id| > 0 &&
            |user_id| > 0 &&
            issued_at < expires_at &&
            issued_at > 0
        }
        
        predicate IsExpired(current_time: Timestamp) reads this {
            current_time >= expires_at || revoked
        }
        
        predicate HasPermission(perm: string) reads this {
            perm in permissions
        }
    }
    
    // === Authorization Trait ===
    trait Authorizer {
        method Authorize(token: SessionToken, required_perm: string,
                        current_time: Timestamp)
            returns (authorized: bool)
            requires token.Valid()
            ensures authorized ==> !token.IsExpired(current_time)
            ensures authorized ==> token.HasPermission(required_perm)
            ensures !authorized ==> 
                token.IsExpired(current_time) || 
                !token.HasPermission(required_perm)
    }
    
    // === Rate Limiting ===
    class RateLimiter {
        var requests: map<UserId, seq<Timestamp>>
        var limit_per_minute: int
        
        predicate Valid() reads this {
            limit_per_minute > 0
        }
        
        method CheckLimit(user: UserId, current_time: Timestamp)
            returns (allowed: bool)
            requires Valid()
            modifies this
            ensures allowed ==> 
                user in old(requests) ==> 
                    |filter_recent(old(requests[user]), current_time)| < limit_per_minute
    }
    
    function filter_recent(timestamps: seq<Timestamp>, now: Timestamp): seq<Timestamp> {
        seq(|timestamps|, i requires 0 <= i < |timestamps| => 
            if now - timestamps[i] < 60 then timestamps[i] else 0)
    }
}
```

---

## 5. Implementation Plan

### File Structure

```
inspecthor-ide-backend/
└── assets/
    └── preludes/
        ├── banking.dfy
        ├── healthcare.dfy
        ├── authentication.dfy
        └── README.md
```

### Integration with VC Generator

```python
# core/vc_generator.py
class VCGenerator:
    def __init__(self):
        self.preludes = self._load_preludes()
    
    def _load_preludes(self) -> dict[str, str]:
        """Load domain prelude modules."""
        preludes = {}
        prelude_dir = Path("assets/preludes")
        for file in prelude_dir.glob("*.dfy"):
            preludes[file.stem] = file.read_text()
        return preludes
    
    def generate_with_prelude(self, claim: ClaimAST, domain: str) -> str:
        """Generate VCs with domain prelude included."""
        prelude = self.preludes.get(domain, "")
        vcs = self._generate_vcs(claim)
        return f"include \"{domain}.dfy\"\n\n{vcs}"
```

---

## 6. Verification Plan

### Automated Tests
1. Each prelude compiles without errors
2. Example implementations pass verification
3. Deliberately incorrect implementations fail

### Example Test Cases

```dafny
// test_banking.dfy
include "banking.dfy"

class TestBank extends Banking.TransferInterface {
    method Transfer(from: Banking.Account, to: Banking.Account, 
                   amount: Banking.Currency)
        returns (success: bool)
    {
        success := from.Withdraw(amount);
        if success {
            to.Deposit(amount);
        }
    }
}

method TestTransfer() {
    var acc1 := new Banking.Account(100.0);
    var acc2 := new Banking.Account(50.0);
    var bank := new TestBank();
    
    var result := bank.Transfer(acc1, acc2, 30.0);
    assert result;
    assert acc1.balance == 70.0;
    assert acc2.balance == 80.0;
}
```
