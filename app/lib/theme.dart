import 'package:flutter/material.dart';

/// Paleta del icono (§11 del contrato). Modo oscuro por defecto porque la app
/// se usa en campo, a pleno sol: alto contraste.
class AppColors {
  static const Color night0 = Color(0xFF0A1730); // cielo nocturno (fondo)
  static const Color night1 = Color(0xFF183468); // cielo nocturno (superficies)
  static const Color gold = Color(0xFFFFA842); // oro (acento primario)
  static const Color cyan = Color(0xFF7AE4FF); // nodo cian (datos)
  static const Color green = Color(0xFF2FBF71); // Arrancar
  static const Color red = Color(0xFFE4573D); // Abortar / aviso
  static const Color blue = Color(0xFF3E82F7); // Finalizado

  static const Color text = Color(0xFFE8EEF9);
  static const Color textDim = Color(0xFF9FB2D0);

  // Fondo de los paneles tipo OLED del panel principal.
  static const Color oledBg = Color(0xFF06101F);
}

ThemeData buildDarkTheme() {
  const scheme = ColorScheme.dark(
    primary: AppColors.gold,
    onPrimary: AppColors.night0,
    secondary: AppColors.cyan,
    onSecondary: AppColors.night0,
    surface: AppColors.night1,
    onSurface: AppColors.text,
    error: AppColors.red,
    onError: Colors.white,
  );

  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: scheme,
    scaffoldBackgroundColor: AppColors.night0,
    canvasColor: AppColors.night0,
    dividerColor: const Color(0x33FFFFFF),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.night0,
      foregroundColor: AppColors.text,
      elevation: 0,
      centerTitle: false,
    ),
    // Nota: no se fija `cardTheme` a proposito. El tipo del tema de Card ha
    // cambiado de nombre entre versiones de Flutter (CardTheme/CardThemeData);
    // dejarlo en el default de Material 3 evita romper la compilacion. Las
    // tarjetas heredan un tono oscuro coherente del colorScheme.
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      backgroundColor: AppColors.night1,
      selectedItemColor: AppColors.gold,
      unselectedItemColor: AppColors.textDim,
      type: BottomNavigationBarType.fixed,
    ),
    drawerTheme: const DrawerThemeData(backgroundColor: AppColors.night1),
    snackBarTheme: const SnackBarThemeData(
      backgroundColor: AppColors.night1,
      contentTextStyle: TextStyle(color: AppColors.text),
      behavior: SnackBarBehavior.floating,
    ),
    textTheme: const TextTheme(
      bodyMedium: TextStyle(color: AppColors.text),
      bodySmall: TextStyle(color: AppColors.textDim),
      titleMedium: TextStyle(color: AppColors.text, fontWeight: FontWeight.w600),
    ),
    inputDecorationTheme: const InputDecorationTheme(
      border: OutlineInputBorder(),
      isDense: true,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: AppColors.gold,
        foregroundColor: AppColors.night0,
      ),
    ),
  );
}
