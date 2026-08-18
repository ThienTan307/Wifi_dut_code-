#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <string>
#include <cmath>
#include <map>
#include <algorithm>

struct DataPoint {
    std::string location;
    std::map<std::string, float> rssiMap;
};

struct DistanceResult {
    double distance;
    std::string location;
};

bool compareDistance(const DistanceResult& a, const DistanceResult& b) {
    return a.distance < b.distance;
}

std::vector<DataPoint> loadDataset(const std::string& filename) {
    std::vector<DataPoint> dataset;
    std::ifstream file(filename);
    std::string line;

    while (std::getline(file, line)) {
        if (line.empty()) continue;
        std::stringstream ss(line);
        std::string location, pair;
        std::getline(ss, location, ',');
        
        DataPoint point;
        point.location = location;
        
        while (std::getline(ss, pair, ',')) {
            size_t colonPos = pair.find(':');
            if (colonPos != std::string::npos) {
                std::string bssid = pair.substr(0, colonPos);
                float rssi = std::stof(pair.substr(colonPos + 1));
                point.rssiMap[bssid] = rssi;
            }
        }
        dataset.push_back(point);
    }
    return dataset;
}

std::string predictKNN(const std::map<std::string, float>& currentRssi, const std::vector<DataPoint>& dataset, int k) {
    std::vector<DistanceResult> distances;
    
    for (const auto& point : dataset) {
        double dist = 0.0;
        for (const auto& kv : currentRssi) {
            const std::string& bssid = kv.first;
            float currentVal = kv.second;
            float trainVal = -100.0; 
            
            if (point.rssiMap.count(bssid)) {
                trainVal = point.rssiMap.at(bssid);
            }
            dist += std::pow(currentVal - trainVal, 2);
        }
        distances.push_back({std::sqrt(dist), point.location});
    }

    std::sort(distances.begin(), distances.end(), compareDistance);
    
    std::map<std::string, int> locationCounts;
    int maxCount = 0;
    std::string bestLocation = "Unknown";
    
    for (int i = 0; i < k && i < distances.size(); i++) {
        std::string loc = distances[i].location;
        locationCounts[loc]++;
        if (locationCounts[loc] > maxCount) {
            maxCount = locationCounts[loc];
            bestLocation = loc;
        }
    }
    return bestLocation;
}

int main() {
    std::vector<DataPoint> dataset = loadDataset("../PC_Offline_Collector/dataset_train.txt");
    
    std::map<std::string, float> testRssi;
    testRssi["00:11:22:33:44:55"] = -45.0;
    
    std::string predictedLocation = predictKNN(testRssi, dataset, 5);
    std::cout << predictedLocation << std::endl;
    
    return 0;
}