#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <cmath>

using namespace std;

// Parametrii sistemului optimizati pentru hardware
#define WINDOW_SIZE 16          
#define PRAG_ACCELERATIE 3.0 
#define COOLDOWN_SAMPLES 30     // ~1.5 secunde de ignorare a suspensiei la 20Hz

// ---------------------------------------------------------
// FUNCȚIA CORE PENTRU FPGA (Top-Level Function pentru Vitis)
// ---------------------------------------------------------
int detectie_groapa(float acc_z) {
    // Directivă HLS pentru a procesa un eșantion per ciclu de ceas
    #pragma HLS PIPELINE II=1
    
    static float fereastra[WINDOW_SIZE] = {0};
    static float suma = 0.0f;
    static int index = 0;
    static bool buffer_plin = false;
    static int cooldown = 0; // Variabilă statică pentru blocarea oscilațiilor

    // 1. Optimizare O(1): Scădem valoarea veche care iese din fereastră
    float valoare_veche = fereastra[index];
    suma -= valoare_veche;

    // 2. Adăugăm valoarea nouă în vector și în sumă
    fereastra[index] = acc_z;
    suma += acc_z;

    // 3. Incrementare circulară a indexului
    index++;
    if (index >= WINDOW_SIZE) {
        index = 0;
        buffer_plin = true;
    }

    // Blocăm detecțiile până când fereastra se umple complet prima dată
    if (!buffer_plin) return 0;

    // 4. Dacă suntem în perioada de recuperare (cooldown), ignorăm șocurile
    if (cooldown > 0) {
        cooldown--;
        return 0;
    }

    // 5. Calculăm media mobilă și diferența locală
    float media = suma / WINDOW_SIZE; 
    float diff = acc_z - media;

    // 6. Decizie de clasificare bazată pe semnul deviației
    if (std::abs(diff) > PRAG_ACCELERATIE) {
        cooldown = COOLDOWN_SAMPLES; // Activăm blocarea pentru următoarele eșantioane
        return diff > 0 ? 1 : -1;
    }

    return 0;
}

// ---------------------------------------------------------
// TESTBENCH / MEDIUL DE SIMULARE SOFTWARE
// ---------------------------------------------------------
int main() {
    ifstream file("Raw Data.csv");
    string line;

    if (!file.is_open()) {
        cerr << "Eroare: Nu am putut deschide Raw Data.csv! Asigura-te ca fisierul este in acelasi director cu executabilul." << endl;
        return 1;
    }

    cout << "--- Incepere Simulare C++ (HLS Compatible) pe date Phyphox ---" << endl;
    int numar_esantion = 0;
    int detectii_totale = 0;
    bool first_line = true;

    while (getline(file, line)) {
        if (line.empty()) continue;
        stringstream ss(line);
        string item;
        float timp, ax, ay, az, abs_acc;

        if (first_line) {
            first_line = false;
            if (line.find("Time") != string::npos || line.find("timp") != string::npos) {
                continue;
            }
        }

        try {
            getline(ss, item, ','); timp = stof(item);
            getline(ss, item, ','); ax = stof(item);
            getline(ss, item, ','); ay = stof(item);
            getline(ss, item, ','); az = stof(item);
            getline(ss, item, ','); abs_acc = stof(item);
        } catch (...) {
            continue; 
        }

        numar_esantion++;
        
        // --- DOWNSAMPLING PENTRU A REGLA FRECVENȚA ---
        if (numar_esantion % 20 != 0) continue; 
        
        int rezultat = detectie_groapa(az);
        
        if (rezultat != 0) {
            detectii_totale++;
            string tip = (rezultat > 0) ? "speedbump" : "pothole";
            cout << "[!] ALERTA: " << tip << " detectat la esantionul "
                 << numar_esantion << " (Timp: " << timp << "s | Acc Z: " << az << " m/s^2)" << endl;
        }
    }

    file.close();
    cout << "--- Simulare Incheiata ---" << endl;
    cout << "Total esantioane procesate: " << numar_esantion << endl;
    cout << "Total anomalii detectate:   " << detectii_totale << endl;
    
    return 0;
}