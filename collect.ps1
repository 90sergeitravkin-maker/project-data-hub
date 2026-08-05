# Собираем код в файл
$outputCode = "project_code.txt"
$outputStructure = "project_structure.txt"

# Очищаем файлы
Set-Content -Path $outputCode -Value "" -Encoding UTF8
Set-Content -Path $outputStructure -Value "" -Encoding UTF8

# Собираем код
Get-ChildItem -Path "src" -Filter "*.py" -Recurse -File | ForEach-Object {
    $relativePath = $_.FullName.Replace((Get-Location).Path, "").TrimStart("\")

    Add-Content -Path $outputCode -Value "----------------------------------------" -Encoding UTF8
    Add-Content -Path $outputCode -Value ("FILE: " + $relativePath) -Encoding UTF8
    Add-Content -Path $outputCode -Value "----------------------------------------" -Encoding UTF8

    Get-Content -Path $_.FullName -Encoding UTF8 | Add-Content -Path $outputCode -Encoding UTF8
    Add-Content -Path $outputCode -Value "" -Encoding UTF8
}

# Собираем структуру проекта
Get-ChildItem -Recurse |
    Select-Object FullName |
    ForEach-Object {
        $_ -replace [regex]::Escape($PWD.Path), ''
    } |
    Out-File -FilePath $outputStructure -Encoding UTF8

Write-Host "Сбор завершен:"
Write-Host "Код сохранен в: $outputCode"
Write-Host "Структура сохранена в: $outputStructure"