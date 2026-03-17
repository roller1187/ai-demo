package ai-demo.detection;

import org.eclipse.microprofile.rest.client.inject.RestClient;
import org.jboss.resteasy.reactive.RestForm;
import jakarta.inject.Inject;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import java.io.File;

@Path("/scan")
public class ScannerResource {

    @Inject
    @RestClient
    DetectionClient detectionClient;

    @POST
    @Consumes(MediaType.MULTIPART_FORM_DATA)
    @Produces(MediaType.APPLICATION_JSON)
    public DetectionResponse scanImage(@RestForm("file") File file) {
        // Forward the file to the Python Model Container
        return detectionClient.analyze(file);
    }
}
