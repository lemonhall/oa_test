function bindCreateSubmit() {
  $("#createBtn").onclick = async () => {
    setError($("#createError"), "");
    const wfKey = $("#workflowKey").value;
    const wf = workflowsByKey[wfKey];
    const type = wf?.request_type || "generic";
    let title = $("#reqTitle").value.trim();
    let body = $("#reqBody").value.trim();
    let payload = null;

    const builder = createPayloadBuilders[type];
    if (builder) {
      const built = builder() || {};
      if (built.error) {
        setError($("#createError"), built.error);
        return;
      }
      payload = built.payload || null;
      title = title || "";
      body = body || "";
    } else {
      if (!title || !body) {
        setError($("#createError"), "标题和内容不能为空");
        return;
      }
    }

    try {
      const created = await api("/api/requests", { method: "POST", body: { workflow: wfKey, type, title, body, payload } });
      const file = $("#attachFile").files && $("#attachFile").files[0];
      if (file) {
        const content_base64 = await readFileAsBase64(file);
        await api(`/api/requests/${created.id}/attachments`, {
          method: "POST",
          body: {
            filename: file.name,
            content_type: file.type || "application/octet-stream",
            content_base64,
          },
        });
      }
      resetCreateForm();
      currentTab = "requests";
      setTab("requests");
    } catch (e) {
      setError($("#createError"), e.code || "提交失败");
    }
  };
}

