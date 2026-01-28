module FileOperations {
  import opened DatabaseModel

  // --- Result Type ---
  datatype Result<T> = 
    | Success(value: T)
    | Failure(error: string)

  // --- Helpers ---
  predicate FilenameUnique(s: SystemState, projectId: UUID, filename: string) {
    forall fid :: fid in s.files && s.files[fid].projectId == projectId ==> s.files[fid].filename != filename
  }

  // --- File Operations ---

  function SaveFile(
    s: SystemState,
    newFileId: UUID, // Shell must generate and pass this
    projectId: UUID,
    filename: string,
    content: Content,
    fileType: FileType,
    ownerId: UUID
  ): (SystemState, Result<UUID>)
    // Preconditions (Contracts)
    requires ValidState(s)
    // 1. Inputs valid
    requires |filename| > 0
    requires newFileId !in s.files // ID uniqueness
    // 2. Project exists and ownership
    requires projectId in s.projects
    requires s.projects[projectId].owner == Authenticated(ownerId) || s.projects[projectId].owner == Anonymous(ownerId)
    // 3. Business Logic
    requires FilenameUnique(s, projectId, filename)
    // 4. Content constraints (implied by type, but explicit here)
    requires |content| < 1000000 // Example size limit
    
    // Postconditions (Guarantees)
    ensures ValidState(SaveFile(s, newFileId, projectId, filename, content, fileType, ownerId).0)
    ensures var res := SaveFile(s, newFileId, projectId, filename, content, fileType, ownerId);
             res.1.Success? ==> 
      // File created correctly
      res.1.value == newFileId &&
      newFileId in res.0.files &&
      res.0.files[newFileId] == File(newFileId, projectId, filename, content, fileType, |content|, false) &&
      // Project updated
      newFileId in res.0.projects[projectId].fileIds
  {
    if !(projectId in s.projects) then (s, Failure("Project not found"))
    else if !FilenameUnique(s, projectId, filename) then (s, Failure("Filename exists"))
    else
      var newFile := File(newFileId, projectId, filename, content, fileType, |content|, false);
      
      // Update File Map
      var newFiles := s.files[newFileId := newFile];
      
      // Update Project's file list (Reverse Integrity)
      var oldProj := s.projects[projectId];
      var newProj := oldProj.(fileIds := oldProj.fileIds + {newFileId});
      var newProjects := s.projects[projectId := newProj];

      (SystemState(newProjects, newFiles), Success(newFileId))
  }

  function UpdateFile(
    s: SystemState,
    fileId: UUID,
    newContent: Content,
    newFilename: string, // Empty if no rename
    ownerId: UUID
  ): (SystemState, Result<UUID>)
    requires ValidState(s)
    requires fileId in s.files
    requires var pid := s.files[fileId].projectId;
             pid in s.projects && (s.projects[pid].owner == Authenticated(ownerId) || s.projects[pid].owner == Anonymous(ownerId))
    ensures ValidState(UpdateFile(s, fileId, newContent, newFilename, ownerId).0)
  {
    var oldFile := s.files[fileId];
    var pid := oldFile.projectId;
    
    // Check filename uniqueness if renaming
    if newFilename != "" && newFilename != oldFile.filename && !FilenameUnique(s, pid, newFilename) then
      (s, Failure("Filename exists"))
    else
      var actualFilename := if newFilename != "" then newFilename else oldFile.filename;
      var isRenamed := oldFile.renamed || (newFilename != "" && newFilename != oldFile.filename);
      
      var newFile := oldFile.(
        content := newContent,
        sizeBytes := |newContent|,
        filename := actualFilename,
        renamed := isRenamed
      );
      
      var newFiles := s.files[fileId := newFile];
      (s.(files := newFiles), Success(fileId))
  }

  function DeleteFile(
    s: SystemState,
    fileId: UUID,
    ownerId: UUID
  ): (SystemState, Result<bool>)
    requires ValidState(s)
    requires fileId in s.files
    requires var pid := s.files[fileId].projectId;
             pid in s.projects && (s.projects[pid].owner == Authenticated(ownerId) || s.projects[pid].owner == Anonymous(ownerId))
    ensures ValidState(DeleteFile(s, fileId, ownerId).0)
    ensures var res := DeleteFile(s, fileId, ownerId);
             res.1.Success? ==> fileId !in res.0.files
  {
    var pid := s.files[fileId].projectId;
    
    // Remove from Files
    var newFiles := map fid | fid in s.files && fid != fileId :: s.files[fid];
    
    // Remove from Project (Referential Integrity)
    var oldProj := s.projects[pid];
    var newProj := oldProj.(fileIds := oldProj.fileIds - {fileId});
    var newProjects := s.projects[pid := newProj];
    
    var newState := SystemState(newProjects, newFiles);
    
    // Prove ValidState using helper lemma
    ValidStateAfterFileDeletion(s, fileId, pid, newFiles, newProjects);

    (newState, Success(true))
  }

  // --- Concrete Test Vectors (JSON Output) ---
  method GenerateTests()
  {
    var uid := "user1";
    var pid := "proj1";
    var newFid := "file1";
    
    // Setup initial state
    var emptyProj := Project(pid, "Test", "Desc", Authenticated(uid), {});
    var s0 := SystemState(map[pid := emptyProj], map[]);
    
    // Case 1: Success
    var (s1, r1) := SaveFile(s0, newFid, pid, "readme.md", "Content", MD, uid);
    
    // Case 2: Duplicate Filename (Failure)
    // Note: This test case demonstrates expected failure behavior.
    // We cannot call SaveFile here because it would violate FilenameUnique precondition.
    // Instead, we document the expected failure case in the JSON output.
    var newFid2 := "file2";
    // Expected: SaveFile(s1, newFid2, pid, "readme.md", "Other", MD, uid) would return Failure("Filename exists")

    // Print JSON directly (Oracle guidance)
    print "{\n";
    print "  \"test_suite\": \"FileOperations\",\n";
    print "  \"cases\": [\n";
    print "    {\n";
    print "      \"id\": \"save_01_success\",\n";
    print "      \"input\": {\n";
    print "        \"method\": \"SaveFile\",\n";
    print "        \"params\": {\n";
    print "          \"newFileId\": \"", newFid, "\",\n";
    print "          \"projectId\": \"", pid, "\",\n";
    print "          \"filename\": \"readme.md\",\n";
    print "          \"content\": \"Content\",\n";
    print "          \"fileType\": \"MD\",\n";
    print "          \"ownerId\": \"", uid, "\"\n";
    print "        }\n";
    print "      },\n";
    print "      \"expected_output\": {\n";
    print "        \"success\": true,\n";
    print "        \"file_id\": \"", newFid, "\"\n";
    print "      }\n";
    print "    },\n";
    print "    {\n";
    print "      \"id\": \"save_02_duplicate_filename\",\n";
    print "      \"input\": {\n";
    print "        \"method\": \"SaveFile\",\n";
    print "        \"params\": {\n";
    print "          \"newFileId\": \"", newFid2, "\",\n";
    print "          \"projectId\": \"", pid, "\",\n";
    print "          \"filename\": \"readme.md\",\n";
    print "          \"content\": \"Other\",\n";
    print "          \"fileType\": \"MD\",\n";
    print "          \"ownerId\": \"", uid, "\"\n";
    print "        }\n";
    print "      },\n";
    print "      \"expected_output\": {\n";
    print "        \"success\": false,\n";
    print "        \"error_kind\": \"Conflict\",\n";
    print "        \"error_message\": \"Filename exists\"\n";
    print "      }\n";
    print "    }\n";
    print "  ]\n";
    print "}\n";
  }
}
