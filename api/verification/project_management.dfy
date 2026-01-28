module ProjectManagement {
  import opened DatabaseModel

  datatype Result<T> = Success(value: T) | Failure(error: string)

  // --- Logic Helpers ---
  // Abstract case-insensitivity for spec (implementation uses .lower())
  function ToLower(s: string): string 

  predicate ProjectNameUnique(s: SystemState, name: string, owner: Owner) {
    forall pid :: pid in s.projects && s.projects[pid].owner == owner 
      ==> ToLower(s.projects[pid].name) != ToLower(name)
  }

  // --- Project Operations ---

  function CreateProject(
    s: SystemState,
    newProjectId: UUID, // Shell must generate
    name: string,
    description: string,
    owner: Owner
  ): (SystemState, Result<UUID>)
    requires ValidState(s)
    requires newProjectId !in s.projects
    requires |name| > 0 && |name| <= 255
    requires |description| <= 1000
    requires ProjectNameUnique(s, name, owner)
    ensures ValidState(result.0)
    ensures result.1.Success? ==> newProjectId in result.0.projects
  {
    if !ProjectNameUnique(s, name, owner) then (s, Failure("Name taken"))
    else
      var newProj := Project(newProjectId, name, description, owner, {});
      var newProjects := s.projects[newProjectId := newProj];
      (s.(projects := newProjects), Success(newProjectId))
  }

  function DeleteProject(
    s: SystemState,
    projectId: UUID,
    ownerId: UUID
  ): (SystemState, Result<bool>)
    requires ValidState(s)
    requires projectId in s.projects
    // Owner check (Auth or Anon)
    requires var p := s.projects[projectId]; 
             p.owner == Authenticated(ownerId) || p.owner == Anonymous(ownerId)
    ensures ValidState(result.0)
    // Post: Project gone
    ensures result.1.Success? ==> projectId !in result.0.projects
    // Post: Cascade - all files belonging to project are gone
    ensures result.1.Success? ==> 
      forall fid :: fid in s.files && s.files[fid].projectId == projectId ==> fid !in result.0.files
  {
    var proj := s.projects[projectId];
    
    // 1. Cascade: Identify files to remove
    var filesToDelete := set fid | fid in s.files && s.files[fid].projectId == projectId;
    
    // 2. Remove files
    var newFiles := map fid | fid in s.files && fid !in filesToDelete :: s.files[fid];
    
    // 3. Remove project
    var newProjects := map pid | pid in s.projects && pid != projectId :: s.projects[pid];
    
    (SystemState(newProjects, newFiles), Success(true))
  }

  // --- Test Vectors (JSON Output) ---
  method GenerateTests()
  {
    var uid := "user1";
    var pid := "proj1";
    var fid := "file1";
    
    // State with 1 project and 1 file
    var p := Project(pid, "A", "D", Authenticated(uid), {fid});
    var f := File(fid, pid, "a.md", "c", MD, 1, false);
    
    var s0 := SystemState(map[pid := p], map[fid := f]);
    
    // Delete Project
    var (s1, r1) := DeleteProject(s0, pid, uid);
    
    // Print JSON directly (Oracle guidance)
    print "{\n";
    print "  \"test_suite\": \"ProjectManagement\",\n";
    print "  \"cases\": [\n";
    print "    {\n";
    print "      \"id\": \"delete_01_cascade\",\n";
    print "      \"input\": {\n";
    print "        \"method\": \"DeleteProject\",\n";
    print "        \"params\": {\n";
    print "          \"projectId\": \"", pid, "\",\n";
    print "          \"ownerId\": \"", uid, "\"\n";
    print "        }\n";
    print "      },\n";
    print "      \"expected_output\": {\n";
    print "        \"success\": true,\n";
    print "        \"project_deleted\": true,\n";
    print "        \"files_cascaded\": [\"", fid, "\"]\n";
    print "      }\n";
    print "    }\n";
    print "  ]\n";
    print "}\n";
  }
}
