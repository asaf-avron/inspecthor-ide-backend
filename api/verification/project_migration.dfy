module ProjectMigration {
  import opened DatabaseModel

  // --- The Core Logic ---
  // Pure function: Takes state, returns NEW state.
  // No database side effects here.
  function MigrateAnonymousProjects(
    s: SystemState, 
    userId: UUID, 
    currentSessionHash: string
  ): SystemState
    requires ValidState(s)
    // Security Lemma included directly in the logic signature
    ensures ValidState(MigrateAnonymousProjects(s, userId, currentSessionHash))
  {
    // 1. Identify Candidate Projects (The 'Filter')
    // Logic: Projects owned by THIS session hash
    var candidates := set pid | 
      pid in s.projects && 
      s.projects[pid].owner == Anonymous(currentSessionHash);

    // 2. Transform State (The 'Map')
    var newProjects := map pid | pid in s.projects :: 
      if pid in candidates then 
        // TRANSITION: Anonymous -> Authenticated
        s.projects[pid].(owner := Authenticated(userId))
      else 
        // PRESERVE: Untouched
        s.projects[pid];

    // 3. Return New State
    s.(projects := newProjects)
  }

  // --- Security Proofs ---
  
  // Theorem: "We never accidentally steal someone else's project"
  lemma Theorem_Isolation(s: SystemState, userId: UUID, hash: string, targetPid: UUID)
    requires ValidState(s)
    requires targetPid in s.projects
    // If the project is NOT owned by the current session hash...
    requires s.projects[targetPid].owner != Anonymous(hash)
    // ...then it MUST NOT change.
    ensures MigrateAnonymousProjects(s, userId, hash).projects[targetPid] == s.projects[targetPid]
  {
    // Dafny proves this automatically based on the function body
  }

  // --- Test Generation (Oracle Requirement) ---
  // Concrete instances for test vector generation
  
  method GenerateTests() returns (testCases: seq<(SystemState, UUID, string, SystemState)>)
  {
    // Test Case 1: Single anonymous project to migrate
    var project1Id := "p1";
    var file1Id := "f1";
    var sessionHash := "hash123";
    var userId := "user456";
    
    var state1 := SystemState(
      projects := map pid := project1Id :: Project(
        projectId := project1Id,
        name := "TestProject",
        description := "Test",
        owner := Anonymous(sessionHash),
        fileIds := {file1Id}
      ),
      files := map fid := file1Id :: File(
        fileId := file1Id,
        projectId := project1Id,
        filename := "test.md",
        content := "content",
        fileType := MD,
        sizeBytes := 7,
        renamed := false
      )
    );
    
    var expectedState1 := MigrateAnonymousProjects(state1, userId, sessionHash);
    
    testCases := [
      (state1, userId, sessionHash, expectedState1)
    ];
  }
}
