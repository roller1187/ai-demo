package ai-demo.detection;

import java.util.List;

public class DetectionResponse {
    public List<Detection> detections;

    public static class Detection {
        public String label;
        public double confidence;
        public List<Double> box; // [xmin, ymin, xmax, ymax]
    }
}
