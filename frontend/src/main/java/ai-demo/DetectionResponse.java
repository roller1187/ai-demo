package com.redhat.aidemo.detection;

import java.util.List;
import com.fasterxml.jackson.annotation.JsonProperty;

public class DetectionResponse {
    public Traveler traveler;
    public List<Detection> detections;
    public String recommendation;

    public static class Traveler {
        public String name;
        public String origin;
        public String dob;
        public History history;
    }

    public static class History {
        @JsonProperty("prior_arrests")
        public int priorArrests;
        public String warrants;
        public String charges;
    }

    public static class Detection {
        public String label;
        public double confidence;
        public List<Double> box;
    }
}