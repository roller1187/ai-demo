package com.redhat.aidemo.detection;

import org.eclipse.microprofile.rest.client.inject.RegisterRestClient;
import org.jboss.resteasy.reactive.RestForm;
import org.jboss.resteasy.reactive.PartType;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.MediaType;
import java.io.File;

@RegisterRestClient(configKey = "detection-api")
@Path("/")
public interface DetectionClient {

    @POST
    @Path("/analyze")
    @Consumes(MediaType.MULTIPART_FORM_DATA)
    DetectionResponse analyze(@RestForm("file") File file);
}
